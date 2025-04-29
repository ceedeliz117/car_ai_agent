from fastapi.responses import JSONResponse


def health_check():
    return JSONResponse(content={"status": "ok"})
