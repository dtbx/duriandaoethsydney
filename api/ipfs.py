from requests import get, post

IPFS_URL = "http://127.0.0.1"

# Ports
PORT_GATEWAY = "8080"
PORT_API = "5001"

# Endpoints
GET = "/ipfs/"
ADD = "/api/v0/add"
PIN = "/api/v0/pin/add"

_build_url = lambda port, endpoint, extra="": f"{IPFS_URL}:{port}{endpoint}{extra}"


def get_file(cid: str):
    resp = get(_build_url(PORT_GATEWAY, GET, cid))
    try:
        resp.raise_for_status()
        return resp.text
    except:
        raise ValueError("Failed to get file")


def add_file(text: str):
    filename = f"llm_{text.__hash__()}.txt"
    files = {"file": (filename, text.encode("utf-8"), "text/plain")}
    resp = post(_build_url(PORT_API, ADD), files=files)
    try:
        resp.raise_for_status()
        return resp.json()["Hash"]
    except:
        raise ValueError("Failed to add file")


if __name__ == "__main__":
    from codetiming import Timer
    from rich import print

    with Timer(name="class", text="[{:0.2f} sec]"):
        print(get_file("Qmc1VuTt6EnoTFG9XBVmxKfo3nXh7PJLVk3x9FfXL3MovW"))
        # print("File:", add_file("Hey, how are you today?"))
