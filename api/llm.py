# from os import getenv
# from dotenv import load_dotenv
# from groq import Groq
# load_dotenv()

from requests import post

VM_URL = "https://curated.aleph.cloud/vm/055e1267fb63f5961e8aee890cfc3f61387deee79f37ce51a44b21feee57d40b/completion"
PARAMS = dict(
    temperature=0.8,
    top_k=40,
    top_p=0.9,
    n_predict=-1,
    repeat_penalty=1.01,
    repeat_last_n=0.01,
    slot_id=-1,
    cache_prompt=False,
    use_default_badwordsids=False,
    stop=["<|", "user:"],
)
SYSTEM = "Follow precisely user instructions. Don't explain or comment what you are doing. Your answers are formatted using markdown."


def call(prompt, vm_url=VM_URL):
    data = PARAMS | dict(
        prompt=f"<|system|>\n{SYSTEM}\n<|user|>\n{prompt}\n<|system|>\n"
    )
    resp = post(vm_url, json=data, timeout=300)
    try:
        resp.raise_for_status()
        text = resp.json()["content"]
        return text
    except:
        raise ValueError("Unexpected response")


""" def call(prompt):
    chat_completion = Groq(api_key=getenv("GROQ_API_KEY")).chat.completions.create(
        model="llama3-70b-8192",
        messages=[
            {
                "role": "system",
                "content": SYSTEM,
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
    )
    return chat_completion.choices[0].message.content """


if __name__ == "__main__":
    from codetiming import Timer
    from rich import print

    with Timer(name="class", text="[{:0.2f} sec]"):
        print(call("Hey, how are you today?"))
