"""Use a browser engine to render and extract dynamically loaded table rows."""
from common import rows_from_browser

print(rows_from_browser("/deferred-content"))
