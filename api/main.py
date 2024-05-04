from fastapi import FastAPI
from ipfs import add_file, get_file
from llm import call

app = FastAPI()


@app.get("/completion", tags=["completion"])
async def completion(prompt: str):
    return {"result": call(prompt)}


@app.get("/completion/ipfs", tags=["completion/ipfs"])
async def completion_ipfs(cid: str):
    content = get_file(cid)
    resp = call(content)
    return {"cid": add_file(resp)}


@app.get("/ipfs_add", tags=["ipfs_add"])
async def ipfs_add(text: str):
    return {"cid": add_file(text)}


@app.get("/ipfs/{cid}", tags=["ipfs/{cid}"])
async def ipfs_get(cid: str):
    return get_file(cid)
