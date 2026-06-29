import os
import sys
import contentful
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
from pinecone import Pinecone, ServerlessSpec

load_dotenv()

SPACE_ID       = os.getenv("CONTENTFUL_SPACE_ID")
ACCESS_TOKEN   = os.getenv("CONTENTFUL_ACCESS_TOKEN")
ENVIRONMENT    = os.getenv("ENVIRONMENT")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")

INDEX_NAME = "liberty-dental-kb"

# Seed data — always injected so core flows work even if CMS is sparse
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
    },
]


def get_contentful_client():
    if not SPACE_ID or not ACCESS_TOKEN:
        print("Contentful credentials missing. Using seed data only.")
        return None
    return contentful.Client(SPACE_ID, ACCESS_TOKEN, environment=ENVIRONMENT, timeout_s=30)


def extract_rich_text(node):
    """Recursively extract plain text from a Contentful RichText document node."""
    if not node:
        return ""
    if isinstance(node, str):
        return node
    if isinstance(node, dict):
        if node.get("nodeType") == "text":
            return node.get("value", "")
        return " ".join(extract_rich_text(c) for c in node.get("content", [])).strip()
    if isinstance(node, list):
        return " ".join(extract_rich_text(i) for i in node).strip()
    return ""


def _paginate(client, content_type, extra_params=None):
    """Yield every entry of a given content type, handling pagination."""
    params = {"content_type": content_type, "limit": 200, "skip": 0}
    if extra_params:
        params.update(extra_params)
    while True:
        try:
            page = client.entries(params)
        except Exception as e:
            print(f"  Contentful error fetching {content_type} at skip={params['skip']}: {e}")
            break
        for entry in page:
            yield entry
        params["skip"] += params["limit"]
        if len(page) < params["limit"]:
            break


def fetch_sections(client):
    """
    Fetch all 'section' entries — these hold the real page body text:
    description, primaryContent, secondaryContent, bulletPoints.
    """
    documents = []
    print("Fetching section entries (509 total)...")

    for entry in _paginate(client, "section"):
        fields = entry.fields()
        title = fields.get("title") or "Section"

        parts = []
        for key in ["description", "subTitle", "primaryContent", "secondaryContent"]:
            val = fields.get(key)
            if not val:
                continue
            if isinstance(val, str):
                parts.append(val)
            elif isinstance(val, dict) and val.get("nodeType"):
                text = extract_rich_text(val)
                if text:
                    parts.append(text)

        bullets = fields.get("bulletPoints") or []
        if bullets:
            parts.append(" | ".join(str(b) for b in bullets if b))

        content = " ".join(parts).strip()
        if not content or len(content) < 15:
            continue  # skip sections with no meaningful text

        documents.append({
            "id": entry.sys["id"],
            "title": str(title),
            "content": content,
        })

    print(f"  → {len(documents)} sections with usable text.")
    return documents


def fetch_accordions(client):
    """
    Fetch 'accordion' entries that have a description (the answer).
    These are FAQ pairs — question in title, answer in description.
    Entries with no description are navigation headers (skip them).
    """
    documents = []
    print("Fetching accordion/FAQ entries (209 total)...")

    for entry in _paginate(client, "accordion"):
        fields = entry.fields()
        question = fields.get("title") or fields.get("question") or ""

        answer_raw = fields.get("description") or fields.get("answer")
        if not answer_raw:
            continue  # navigation header — no answer text

        if isinstance(answer_raw, str):
            answer = answer_raw
        elif isinstance(answer_raw, dict) and answer_raw.get("nodeType"):
            answer = extract_rich_text(answer_raw)
        else:
            continue

        if not answer or len(answer) < 10:
            continue

        content = f"Question: {question}\nAnswer: {answer}" if question else answer

        documents.append({
            "id": entry.sys["id"],
            "title": str(question) if question else "FAQ",
            "content": content,
        })

    print(f"  → {len(documents)} FAQ entries with answers.")
    return documents


def fetch_pages(client):
    """
    Fetch 'page' entries for their metaTitle + metaDescription.
    These are brief but useful for matching page-level queries.
    """
    documents = []
    print("Fetching page entries (230 total)...")

    for entry in _paginate(client, "page", {"locale": "en-US"}):
        fields = entry.fields()
        title   = fields.get("metaTitle") or fields.get("title") or ""
        desc    = fields.get("metaDescription") or ""
        route   = fields.get("routeName") or ""

        if isinstance(desc, dict) and desc.get("nodeType"):
            desc = extract_rich_text(desc)

        parts = []
        if title:
            parts.append(str(title))
        if desc and isinstance(desc, str):
            parts.append(desc)
        if route and isinstance(route, str):
            parts.append(f"Page URL: {route}")

        content = " ".join(parts).strip()
        if not content or len(content) < 15:
            continue

        documents.append({
            "id": entry.sys["id"],
            "title": str(title) if title else "Page",
            "content": content,
        })

    print(f"  → {len(documents)} pages with usable text.")
    return documents


def fetch_cards(client):
    """
    Fetch 'card' entries — 323 cards that may contain titles + descriptions.
    """
    documents = []
    print("Fetching card entries (323 total)...")

    for entry in _paginate(client, "card"):
        fields = entry.fields()
        title = fields.get("title") or fields.get("heading") or ""

        parts = []
        for key in ["description", "content", "body", "subTitle", "text"]:
            val = fields.get(key)
            if not val:
                continue
            if isinstance(val, str):
                parts.append(val)
            elif isinstance(val, dict) and val.get("nodeType"):
                text = extract_rich_text(val)
                if text:
                    parts.append(text)

        if title:
            parts.insert(0, str(title))

        content = " ".join(parts).strip()
        if not content or len(content) < 15:
            continue

        documents.append({
            "id": entry.sys["id"],
            "title": str(title) if title else "Card",
            "content": content,
        })

    print(f"  → {len(documents)} cards with usable text.")
    return documents


def build_knowledge_base(client):
    """
    Combine all Contentful content types into one de-duplicated document list,
    then append the seed data for guaranteed core-flow coverage.
    """
    all_docs = []

    if client:
        all_docs += fetch_sections(client)
        all_docs += fetch_accordions(client)
        all_docs += fetch_pages(client)
        all_docs += fetch_cards(client)

    # De-duplicate by Contentful entry ID
    seen_ids = {doc["id"] for doc in all_docs}

    # Always inject seed data
    print("Injecting core seed knowledge items...")
    for seed in SEED_DATA:
        if seed["id"] not in seen_ids:
            all_docs.append(seed)
            seen_ids.add(seed["id"])

    print(f"\nTotal documents to index: {len(all_docs)}")
    return all_docs


def initialize_pinecone():
    if not PINECONE_API_KEY:
        print("Error: PINECONE_API_KEY is not set.")
        sys.exit(1)

    pc = Pinecone(api_key=PINECONE_API_KEY)
    existing = [idx["name"] for idx in pc.list_indexes()]

    if INDEX_NAME not in existing:
        print(f"Creating Pinecone index '{INDEX_NAME}'...")
        pc.create_index(
            name=INDEX_NAME,
            dimension=384,
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region="us-east-1"),
        )
        print("Index created.")
    else:
        print(f"Pinecone index '{INDEX_NAME}' already exists.")

    return pc.Index(INDEX_NAME)


def process_and_upload():
    print("=" * 55)
    print("LIBERTY DENTAL PLAN — DATA PIPELINE")
    print("=" * 55)

    print("\nInitializing components...")
    model  = SentenceTransformer("all-MiniLM-L6-v2")
    index  = initialize_pinecone()
    client = get_contentful_client()

    documents = build_knowledge_base(client)

    if not documents:
        print("No documents found. Exiting.")
        return

    print(f"\nGenerating embeddings for {len(documents)} documents...")

    batch_size = 50
    total_batches = (len(documents) + batch_size - 1) // batch_size

    for i in range(0, len(documents), batch_size):
        batch    = documents[i : i + batch_size]
        ids      = [doc["id"] for doc in batch]
        texts    = [f"Title: {doc['title']}\nContent: {doc['content']}" for doc in batch]
        metadata = [{"title": doc["title"], "content": doc["content"]} for doc in batch]

        embeddings = model.encode(texts).tolist()
        records    = list(zip(ids, embeddings, metadata))

        batch_num = i // batch_size + 1
        print(f"  Upserting batch {batch_num}/{total_batches} ({len(batch)} docs)...")
        index.upsert(vectors=records)

    print("\n" + "=" * 55)
    print(f"Pipeline complete! {len(documents)} documents indexed into Pinecone.")
    print("=" * 55)


if __name__ == "__main__":
    process_and_upload()
