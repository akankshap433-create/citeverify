import time

def timed_import(name, func):
    t0 = time.time()
    func()
    print(f"Imported {name} in {time.time() - t0:.2f}s")

timed_import("schemas", lambda: __import__("app.schemas"))
timed_import("pdf_parser", lambda: __import__("app.services.pdf_parser"))
timed_import("claim_extractor", lambda: __import__("app.services.claim_extractor"))
timed_import("research_api", lambda: __import__("app.services.research_api"))
timed_import("verifier", lambda: __import__("app.services.verifier"))
timed_import("db", lambda: __import__("app.services.db"))
timed_import("report_gen", lambda: __import__("app.services.report_gen"))
timed_import("main", lambda: __import__("app.main"))
print("All imports finished!")
