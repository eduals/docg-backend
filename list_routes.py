from app import create_app
import urllib.parse

app = create_app()
print(f"{'Endpoint':<50} {'Methods':<20} {'Rule'}")
print("-" * 100)
for rule in app.url_map.iter_rules():
    methods = ','.join(sorted(rule.methods))
    print(f"{rule.endpoint:<50} {methods:<20} {rule}")
