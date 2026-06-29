import os
import contentful
from dotenv import load_dotenv

load_dotenv()

client = contentful.Client(
    os.getenv("CONTENTFUL_SPACE_ID"),
    os.getenv("CONTENTFUL_ACCESS_TOKEN"),
    environment=os.getenv("ENVIRONMENT")
)

print("=" * 55)
print("CONTENTFUL SPACE DIAGNOSTIC")
print("=" * 55)

# Count every content type
print("\n--- ENTRY COUNTS BY CONTENT TYPE ---")
for ct in ["page", "section", "accordion", "newsletters", "memberTransfer", "urlRedirection", "card", "iconText"]:
    try:
        entries = client.entries({'content_type': ct, 'limit': 1})
        total = entries.total if hasattr(entries, 'total') else len(entries)
        print(f"  {ct:20s}: {total} entries")
    except Exception as e:
        print(f"  {ct:20s}: NOT FOUND ({e})")

# Preview 5 section entries
print("\n--- SECTION ENTRIES PREVIEW (first 5) ---")
try:
    sections = client.entries({'content_type': 'section', 'limit': 5})
    print(f"Total section entries: {sections.total if hasattr(sections, 'total') else '?'}")
    for i, s in enumerate(sections, 1):
        f = s.fields()
        print(f"\n[{i}] Title: {f.get('title', 'N/A')}")
        print(f"    ParentRoute       : {f.get('parentRoute', 'N/A')}")
        print(f"    Has description   : {bool(f.get('description'))}")
        print(f"    Has primaryContent: {bool(f.get('primaryContent'))}")
        print(f"    Has secondaryContent: {bool(f.get('secondaryContent'))}")
        bp = f.get('bulletPoints', [])
        print(f"    BulletPoints count: {len(bp)}")
        if bp:
            print(f"    First bullet      : {bp[0][:80]}")
        acc = f.get('accordians', [])
        print(f"    Accordions count  : {len(acc)}")
except Exception as e:
    print(f"  ERROR fetching sections: {e}")

# Preview accordion entries
print("\n--- ACCORDION (FAQ) ENTRIES PREVIEW (first 5) ---")
try:
    accordions = client.entries({'content_type': 'accordion', 'limit': 5})
    total = accordions.total if hasattr(accordions, 'total') else '?'
    print(f"Total accordion entries: {total}")
    for i, a in enumerate(accordions, 1):
        f = a.fields()
        q = f.get('title') or f.get('question') or f.get('heading') or 'N/A'
        has_answer = bool(f.get('answer') or f.get('description') or f.get('content'))
        print(f"\n[{i}] Question : {str(q)[:80]}")
        print(f"    Has answer: {has_answer}")
        print(f"    All fields: {list(f.keys())}")
except Exception as e:
    print(f"  ERROR or not found: {e}")

# Preview newsletters
print("\n--- NEWSLETTER/NEWS ARTICLE PREVIEW (first 3) ---")
try:
    news = client.entries({'content_type': 'newsletters', 'limit': 3})
    total = news.total if hasattr(news, 'total') else '?'
    print(f"Total newsletter entries: {total}")
    for i, n in enumerate(news, 1):
        f = n.fields()
        print(f"\n[{i}] Title   : {f.get('title', 'N/A')}")
        print(f"    Category: {f.get('category', 'N/A')}")
        print(f"    Has content (RT): {bool(f.get('content'))}")
except Exception as e:
    print(f"  ERROR fetching newsletters: {e}")

# Preview page entries
print("\n--- PAGE ENTRIES PREVIEW (first 5) ---")
try:
    pages = client.entries({'content_type': 'page', 'limit': 5})
    total = pages.total if hasattr(pages, 'total') else '?'
    print(f"Total page entries: {total}")
    for i, p in enumerate(pages, 1):
        f = p.fields()
        print(f"\n[{i}] metaTitle  : {f.get('metaTitle', 'N/A')}")
        print(f"    routeName  : {f.get('routeName', 'N/A')}")
        sections_linked = f.get('sections', [])
        print(f"    sections linked: {len(sections_linked)}")
except Exception as e:
    print(f"  ERROR fetching pages: {e}")

print("\n" + "=" * 55)
print("DIAGNOSTIC COMPLETE")
print("=" * 55)
