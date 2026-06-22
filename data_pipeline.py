import os
import sys
import contentful
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
from pinecone import Pinecone, ServerlessSpec

# Load environment variables
load_dotenv()

# Configuration
SPACE_ID = os.getenv("CONTENTFUL_SPACE_ID")
ACCESS_TOKEN = os.getenv("CONTENTFUL_ACCESS_TOKEN")
ENVIRONMENT = os.getenv("ENVIRONMENT")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")

INDEX_NAME = "liberty-dental-kb"

# Fallback/Seed Data if Contentful entries don't have enough text
# This aligns with the POC's focus on high-value actions
SEED_DATA = [
    {
        "id": "kb_001",
        "title": "Mobile App Download",
        "content": "You can manage your Liberty Dental Plan on the go! Download our mobile app to access your ID card, find a dentist, and check your benefits directly from your phone. Apple and Android links are available.",
    },
    {
        "id": "kb_002",
        "title": "Individual and family dental plans",
        "content": "We offer robust individual and family dental plans with great benefits such as no deductibles, no waiting periods, and emergency coverage. You can explore costs and buy a plan directly through our Shop Plans portal.",
    },
    {
        "id": "kb_003",
        "title": "Member support & Login",
        "content": "To view your ID card, check covered services, or track submitted claims, please log in to the secure Member Portal. Note: As a public website assistant, I cannot access your personal account information.",
    },
    {
        "id": "kb_004",
        "title": "Find a dentist",
        "content": "Looking for an in-network dentist? You can easily search for a highly-rated dental care provider near your location using our Find a Dentist tool on the public website.",
    },
    {
        "id": "kb_005",
        "title": "Teledentistry & Emergencies",
        "content": "Experiencing a dental emergency or need a consultation? Liberty members can utilize Teledentistry to consult with a licensed dentist 24/7 from a computer or mobile device at no cost.",
    },
    {
        "id": "kb_006",
        "title": "Provider guidance",
        "content": "Dental providers are welcome to learn how to join Liberty's network through our public provider page. We boast efficient claims processing, dedicated Provider Relations support, and an easy-to-use Provider Portal.",
    },
    {
        "id": "kb_007",
        "title": "Broker guidance",
        "content": "Brokers can use the Liberty Dental Plan broker page to learn about selling our competitive plans with low costs. Select your state to apply or contact our client services team.",
    },
    {
        "id": "kb_008",
        "title": "Grievance or appeal",
        "content": "We take your concerns seriously. For grievance or appeal information, please visit the File a Grievance or Appeal page on our website where you can find the necessary forms and instructions.",
    }
]

def get_contentful_client():
    if not SPACE_ID or not ACCESS_TOKEN:
        print("Contentful credentials missing in .env. Skipping real extraction.")
        return None
    return contentful.Client(
        SPACE_ID,
        ACCESS_TOKEN,
        environment=ENVIRONMENT
    )

def fetch_contentful_documents(client):
    """
    Fetches entries from Contentful and formats them for Pinecone.
    """
    documents = []
    
    if client:
        print("Fetching entries from Contentful...")
        try:
            entries = client.entries()
            for entry in entries:
                # Extracting meaningful text. Contentful models can vary, 
                # so we check for common text fields (metaTitle, metaDescription, title, content, answer)
                fields = entry.fields()
                
                title = fields.get('title') or fields.get('metaTitle') or "Untitled Document"
                
                # Try to build a substantial content string
                content_parts = []
                
                # Check known rich-text/long-text fields first
                for key in ['metaDescription', 'subTitle', 'answer', 'description', 'content']:
                    val = fields.get(key)
                    if val and isinstance(val, str):
                        content_parts.append(val)
                
                # If we still have nothing, just grab whatever string fields exist (like 'url' or 'slug')
                if not content_parts:
                    for key, val in fields.items():
                        if key not in ['title', 'metaTitle'] and isinstance(val, str):
                            content_parts.append(f"{key}: {val}")
                
                content = " ".join(content_parts).strip()
                
                # Even if content is just a URL, we should index it with the title
                if not content:
                    content = title
                    
                documents.append({
                        "id": entry.sys['id'],
                        "title": title,
                        "content": content
                    })
        except Exception as e:
            print(f"Failed to fetch Contentful entries: {e}")
            
    # Always inject our seed data to guarantee the POC core flows work 
    # and to simulate a rich knowledge base.
    # print("Injecting core knowledge base seeds...")
    # for seed in SEED_DATA:
    #     # Avoid duplicate IDs if they clash with Contentful somehow
    #     documents.append(seed)
        
    return documents

def initialize_pinecone():
    """Initializes Pinecone index."""
    if not PINECONE_API_KEY:
        print("Error: PINECONE_API_KEY is not set.")
        sys.exit(1)
        
    pc = Pinecone(api_key=PINECONE_API_KEY)
    
    # Check if index exists, if not create it
    existing_indexes = [index_info["name"] for index_info in pc.list_indexes()]
    if INDEX_NAME not in existing_indexes:
        print(f"Creating Pinecone index '{INDEX_NAME}'...")
        # sentence-transformers 'all-MiniLM-L6-v2' outputs 384 dimensions
        pc.create_index(
            name=INDEX_NAME,
            dimension=384,
            metric="cosine",
            spec=ServerlessSpec(
                cloud="aws",
                region="us-east-1"
            )
        )
        print("Index created.")
    else:
        print(f"Pinecone index '{INDEX_NAME}' already exists.")
        
    return pc.Index(INDEX_NAME)

def process_and_upload():
    print("Initializing components...")
    model = SentenceTransformer('all-MiniLM-L6-v2')
    index = initialize_pinecone()
    client = get_contentful_client()
    
    documents = fetch_contentful_documents(client)
    
    if not documents:
        print("No documents found to process.")
        return
        
    print(f"Generating embeddings for {len(documents)} documents...")
    
    # Upsert in batches
    batch_size = 50
    for i in range(0, len(documents), batch_size):
        batch = documents[i:i + batch_size]
        
        ids = [doc["id"] for doc in batch]
        texts = [f"Title: {doc['title']}\nContent: {doc['content']}" for doc in batch]
        metadata = [{"title": doc["title"], "content": doc["content"]} for doc in batch]
        
        # Generate embeddings
        embeddings = model.encode(texts).tolist()
        
        # Format for pinecone: List of (id, vector, metadata)
        records = list(zip(ids, embeddings, metadata))
        
        print(f"Upserting batch {i//batch_size + 1}...")
        index.upsert(vectors=records)
        
    print("Data pipeline completed successfully!")

if __name__ == "__main__":
    process_and_upload()
