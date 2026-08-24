import boto3
import json
import logging
import random
import os

from datetime import datetime, timezone

from botocore.exceptions import ClientError
from botocore.config import Config

logger = logging.getLogger()
logger.setLevel(logging.INFO)

BUCKET_NAME = "myths-agent-aws-dev-challenge"
AWS_REGION = "eu-north-1"
MODEL_ID = "amazon.nova-lite-v1:0"
FALLBACK_MODEL_ID = "amazon.nova-micro-v1:0"
MANIFEST_KEY = "manifest.json"

_botos_config = Config(region_name=AWS_REGION, retries={"max_attempts": 3, "mode": "adaptive"})

bedrock_rt = boto3.client("bedrock-runtime", config=_botos_config)
s3 = boto3.client("s3", config=_botos_config)

with open(os.path.join(os.path.dirname(__file__), "content_library.json")) as f:
    LIBRARY = json.load(f)

def pick_random_pair():
    myth = random.choice(LIBRARY["myths"])
    trivia = random.choice(LIBRARY["tech_trivia"])

    return myth, trivia

def build_prompt(myth, trivia):
    return (
        "You are a witty technical storyteller who writes short parables for software "
        "engineers. Blend the mythological story below with the computer-science concept "
        "below into a single, coherent, whimsical fable of 100-300 words. End with a short "
        "'Moral for Engineers' takeaway (1-2 sentences). Do not explain that you are "
        "combining two topics -- just tell the story.\n\n"
        f"MYTH: {myth['title']} -- {myth['summary']}\n\n"
        f"TECH CONCEPT: {trivia['title']} -- {trivia['detail']}\n"
    )

def generate_story(myth, trivia):
    prompt = build_prompt(myth=myth, trivia=trivia)

    try:
        return invoke_nova(prompt=prompt, model_id=MODEL_ID)
    except ClientError as err:
        code = err.response.get("Error", {}).get("Code", "")
        logger.warning(f"Main Model failed {code}; falling to fallback model {FALLBACK_MODEL_ID}")
        if code in ("ThrottlingException", "ModelTimeoutException", "ServiceUnavailableException"):
            return invoke_nova(prompt, FALLBACK_MODEL_ID)
        raise


def invoke_nova(prompt, model_id):
    response = bedrock_rt.converse(
        modelId=model_id,
        messages=[
            {
                "role": "user",
                "content": [
                    {"text": prompt}
                ]
            }
        ],
        inferenceConfig={
            "maxTokens": 800,
            "temperature": 0.9,
            "topP": 0.9
        }
    )
    return response["output"]["message"]["content"][0]["text"]

def update_manifest(entry):
    try:
        existing_obj = s3.get_object(Bucket=BUCKET_NAME, Key=MANIFEST_KEY)
        manifest = json.loads(existing_obj["Body"].read())
    except s3.exceptions.NoSuchKey:
        manifest = []
    except ClientError as err:
        if err.response.get("Error", {}).get("Code") == "NoSuchKey":
            manifest = []
        else:
            raise
 
    manifest.append(entry)
 
    s3.put_object(
        Bucket=BUCKET_NAME,
        Key=MANIFEST_KEY,
        Body=json.dumps(manifest, indent=2).encode("utf-8"),
        ContentType="application/json",
    )
    logger.info("manifest.json updated (%d total entries)", len(manifest))
 

def save_artifact(myth, trivia, story_text):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    key = f"compendium/{today}-{myth['id']}-{trivia['id']}.md"
    body = (
        f"# {today}: {myth['title']} meets {trivia['title']}\n\n"
        f"*Myth:* {myth['summary']}\n\n"
        f"*Tech concept:* {trivia['detail']}\n\n---\n\n{story_text}\n"
    )
    s3.put_object(
        Bucket=BUCKET_NAME, Key=key, Body=body.encode("utf-8"),
        ContentType="text/markdown; charset=utf-8",
    )
 
    update_manifest({
        "date": today,
        "key": key,
        "myth": myth["title"],
        "trivia": trivia["title"],
    })
 
    return key
 
 

def handler(event, context):
    myth, trivia = pick_random_pair()
    logger.info("Pairing selected: %s + %s", myth["id"], trivia["id"])
    story_text = generate_story(myth, trivia)
    key = save_artifact(myth, trivia, story_text)
    return {
        "statusCode": 200,
        "body": json.dumps({
        "message": "Artifact generated",
        "s3_key": key,
        "myth": myth["id"],
        "trivia": trivia["id"]
    })
    }
