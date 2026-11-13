from fastapi import FastAPI

app = FastAPI(
    title="LUNA-SCOPE API",
    description="Lunar mission analysis and decision-support services",
    version="0.1.0",
)

@app.get("/health")
def health_check():
    return {"status": "ok", "project": "LUNA-SCOPE"}
