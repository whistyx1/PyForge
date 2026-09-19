from fastapi import FastAPI

app = FastAPI(title='PyForge FastAPI example')

@app.get('/')
def home():
    return {'message': 'Hello from PyForge FastAPI app'}

@app.get('/health')
def health():
    return {'status': 'ok'}