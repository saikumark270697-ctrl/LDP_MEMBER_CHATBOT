import os
import contentful
from dotenv import load_dotenv

load_dotenv()
client = contentful.Client(os.getenv("CONTENTFUL_SPACE_ID"), os.getenv("CONTENTFUL_ACCESS_TOKEN"), environment=os.getenv("ENVIRONMENT"))

entries = client.entries()
print("Content in CMS:")
count = 0
for e in entries:
    fields = e.fields()
    title = fields.get('metaTitle') or fields.get('title')
    desc = fields.get('metaDescription') or ""
    if title:
        print(f"- {title}")
        print(f"  Description: {desc[:100]}...")
        count += 1
print(f"Total useful pages found: {count}")
