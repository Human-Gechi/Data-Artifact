# MythForge

**A daily fable that pairs a myth with a software engineering concept — written by an LLM, stored in S3, served over CloudFront.**

Every morning, a scheduled job picks one myth and one technical idea at random, asks Amazon Bedrock to weave them into a short story, and publishes the result as a static markdown file. A small frontend reads the growing archive and renders each entry as a card, complete with a "Moral for Engineers" at the end.

[![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)]()
[![AWS](https://img.shields.io/badge/AWS-Cloud-232F3E?logo=amazonaws&logoColor=white)]()
[![Bedrock](https://img.shields.io/badge/Amazon%20Bedrock-FF9900?logo=amazonaws&logoColor=white)]()
[![S3](https://img.shields.io/badge/Amazon%20S3-569A31?logo=amazons3&logoColor=white)]()
[![Lambda](https://img.shields.io/badge/AWS%20Lambda-FF9900?logo=awslambda&logoColor=white)]()
[![EventBridge Scheduler](https://img.shields.io/badge/EventBridge%20Scheduler-FF9900?logo=amazonaws&logoColor=white)]()
[![CloudFront](https://img.shields.io/badge/AWS%20CloudFront-8C4FFF?logo=amazonaws&logoColor=white)]()
[![Terraform](https://img.shields.io/badge/Terraform-844FBA?logo=terraform&logoColor=white)]()

---

## Contents

- [What this is](#what-this-is)
- [Tech stack](#tech-stack)
- [How a run works](#how-a-run-works)
- [Architecture](#architecture)
- [AWS resources](#aws-resources)
- [The content library](#the-content-library)
- [The prompt](#the-prompt)
- [The frontend](#the-frontend)
- [Repository layout](#repository-layout)
- [Infrastructure, resource by resource](#infrastructure-resource-by-resource)
- [Access control](#access-control)
- [Deploying it](#deploying-it)
- [Checking that it worked](#checking-that-it-worked)
- [Known limitations](#known-limitations)
- [Challenges encountered](#challenges-encountered)
- [What I learned](#what-i-learned)
- [Possible next steps](#possible-next-steps)
- [Author](#author)

---

## What this is

MythForge is a small, fully automated pipeline with two halves:

1. **A Python Lambda function** (`lambda.py`) that runs once a day, picks a myth and a technical concept from a local JSON library, asks Amazon Bedrock to turn them into a short story, and writes the result to S3.
2. **A static HTML page** (`frontend/index.html`) that fetches the growing list of stories from S3 through CloudFront and displays them, newest first, one card per day.

There's no database, no application server, and no user accounts. The Lambda writes files; CloudFront serves them; a single JSON manifest ties the two together.

## Tech stack

| Tool / Service | Role in this project |
|---|---|
| Python 3.11 | Lambda runtime and the language `lambda.py` is written in |
| boto3 | AWS SDK used to call Bedrock and S3 from inside the Lambda |
| AWS Lambda | Runs the daily generation logic |
| Amazon Bedrock (Nova Lite / Nova Micro) | Generates each story from the prompt, via the Converse API |
| Amazon S3 | Stores the markdown stories, `manifest.json`, and the frontend file |
| Amazon EventBridge Scheduler | Triggers the Lambda once a day on a fixed cron |
| Amazon CloudFront | Serves the bucket's contents publicly over HTTPS |
| Amazon CloudWatch Logs | Captures the Lambda's execution logs |
| AWS IAM | Scopes exactly what the Lambda and the Scheduler are each allowed to do |
| Terraform | Defines and provisions every AWS resource in the project |
| HTML, CSS, vanilla JavaScript | The frontend itself — no framework, no build step |

## How a run works

```
1. EventBridge Scheduler invokes the Lambda function on a fixed schedule.
2. Lambda picks one random myth and one random tech concept from content_library.json.
3. Lambda builds a prompt and calls Bedrock (Converse API) with Amazon Nova Lite.
   - If Nova Lite throttles, times out, or is unavailable, it retries once with Nova Micro.
4. Bedrock returns a 100-300 word story ending in a "Moral for Engineers".
5. Lambda writes the story as a markdown file to S3, under compendium/.
6. Lambda reads manifest.json from S3, appends the new entry, writes it back.
7. The next time someone loads the site, the frontend fetches manifest.json,
   fetches each story's markdown file, and renders a card for it.
```

Each markdown file contains the date, the myth title and summary, the tech concept and its explanation, the generated story, and the moral — all in one document, so the file is readable on its own even outside the frontend.

## Architecture

```
 ┌──────────────────────┐
 │ EventBridge Scheduler │   cron(0 7 * * ? *)  — 07:00 UTC daily
 └──────────┬────────────┘
            │ invokes
            ▼
 ┌──────────────────────┐        ┌───────────────────────┐
 │      AWS Lambda       │ ─────▶ │    Amazon Bedrock      │
 │   myths-agent-handler │        │  Nova Lite → Nova Micro│
 └──────────┬────────────┘        └───────────────────────┘
            │ writes story + manifest.json
            ▼
 ┌──────────────────────┐
 │      Amazon S3        │   myths-agent-aws-dev-challenge
 │  (all public access   │   (fully private bucket)
 │      blocked)         │
 └──────────┬────────────┘
            │ read-only, via Origin Access Control
            ▼
 ┌──────────────────────┐
 │   Amazon CloudFront   │  →  browser fetches index.html,
 │                        │      manifest.json, and each .md file
 └──────────────────────┘
```

The bucket is never exposed directly. CloudFront is the only thing allowed to read from it, enforced by a bucket policy scoped to that one distribution's ARN.

## AWS resources

Everything below is created by Terraform, except Bedrock's foundation models, which are a pre-existing AWS service the Lambda simply calls.

1. **Amazon S3 bucket** — `myths-agent-aws-dev-challenge`, stores stories, the manifest, and the frontend.
2. **S3 bucket public access block** — blocks every form of public access at the bucket level.
3. **S3 bucket policy** — grants read access to CloudFront only, scoped to one distribution's ARN.
4. **S3 object upload** — `frontend/index.html`, uploaded and re-uploaded automatically on change.
5. **IAM role (Lambda)** — `myths-agent-lambda-role`, assumed by `lambda.amazonaws.com`.
6. **IAM policy (Lambda)** — `myths-agent-lambda-policy`, scoped to this bucket, this Lambda's logs, and two specific Bedrock model ARNs.
7. **AWS Lambda function** — `myths-agent-handler`, Python 3.11, runs the daily generation logic.
8. **Amazon Bedrock (used, not provisioned)** — Nova Lite as the primary model, Nova Micro as the fallback.
9. **CloudFront origin access control (OAC)** — lets CloudFront sign requests to S3 with SigV4.
10. **CloudFront distribution** — the public CDN in front of the bucket.
11. **IAM role (Scheduler)** — `myths-agent-scheduler-role`, assumed by `scheduler.amazonaws.com`.
12. **IAM policy (Scheduler)** — `myths-agent-scheduler-invoke-policy`, scoped to `lambda:InvokeFunction` on this one function.
13. **EventBridge Scheduler schedule** — `daily-myths-agent`, `cron(0 7 * * ? *)` UTC, no flexible time window.
14. **Amazon CloudWatch Logs group (implicit)** — created automatically on first invocation; not declared in Terraform, so it isn't managed or destroyed by it either.

## The content library

`content_library.json` holds two flat lists:

| List | Count | Shape |
|---|---|---|
| `myths` | 30 | `id`, `title`, `summary` |
| `tech_trivia` | 30 | `id`, `title`, `detail` |

Myths range from the well-known (Icarus, Prometheus, Pandora's Box) to the more obscure (Procrustes' Bed, the Ouroboros, Yu the Great taming the flood). Tech concepts span classic CS theory (the CAP theorem, the Byzantine Generals Problem, the Two Generals Problem) and everyday engineering folklore (rubber duck debugging, cold starts, magic numbers, technical debt).

Because the pairing is random and independent each run, there are 30 × 30 = **900 possible myth-and-concept combinations** — enough that the same pairing showing up twice is unlikely for a long while, though nothing currently prevents it.

## The prompt

`build_prompt()` gives Bedrock a fixed set of instructions:

- Write a single fable, 100–300 words long.
- Blend the myth and the tech concept naturally — don't explain that two topics are being combined.
- End with a short "Moral for Engineers" (one or two sentences).

## The frontend

`frontend/index.html` is a single self-contained file — no build step, no framework. It:

- Fetches `manifest.json` from amazon s3, sorts entries newest-first, and de-duplicates by date so a given day never shows more than one card.
- Fetches each entry's markdown file and renders it with [marked.js](https://github.com/markedjs/marked), loaded from a CDN.
- Post-processes the rendered HTML to wrap the "Moral for Engineers" line in a styled callout.
- Shows a loading message while fetching, and a plain error message if the manifest or a story fails to load.

The visual style is a dark, purple-led palette (background `#1b1625`, accent `#b298e7`) with teal and pink used only for the myth/concept tag pills. The favicon is an inline SVG data URI, so there's no separate image asset to host.

## Repository layout

```
.
├── README.md
├── lambda.py                 # Handler + Bedrock calls + S3 writes
├── content_library.json      # Myths and tech concepts (bundled into the Lambda zip)
├── frontend/
│   └── index.html            # Static site, uploaded to the bucket by Terraform
└── infra/
    ├── provider.tf           # AWS provider, region
    ├── version.tf            # Terraform + provider version constraints
    ├── main.tf                # Bucket, Lambda, IAM role/policy for the Lambda
    ├── frontend.tf            # CloudFront, OAC, bucket policy, index.html upload
    ├── scheduler.tf           # EventBridge Scheduler + its own IAM role
    └── output.tf              # CloudFront domain, bucket ARN
```

`lambda.py` expects `content_library.json` to sit next to it at deploy time — both files get zipped together into `lambda.zip` one directory above `infra/`, which is where `main.tf` looks for it.

## Infrastructure, resource by resource

| Resource | File | What it does |
|---|---|---|
| `aws_s3_bucket.artifact_bucket` | `main.tf` | Stores story markdown, `manifest.json`, and `index.html`. Bucket name: `myths-agent-aws-dev-challenge`. |
| `aws_s3_bucket_public_access_block` | `main.tf` | Blocks every form of public access at the bucket level. |
| `aws_iam_role.lambda_exec_role` + `aws_iam_policy.lambda_access` | `main.tf` | Lets the Lambda write CloudWatch logs, read/write/list the bucket, and call `bedrock:InvokeModel` / `bedrock:Converse` — scoped to exactly the Nova Lite and Nova Micro model ARNs, nothing else. |
| `aws_lambda_function.myths_agent` | `main.tf` | The function itself: `myths-agent-handler`, Python 3.11, handler `lambda.handler`, deployed from `lambda.zip`. |
| `aws_cloudfront_origin_access_control.artifact_oac` | `frontend.tf` | Lets CloudFront sign requests to S3 with SigV4, so the bucket can trust CloudFront specifically instead of any anonymous caller. |
| `aws_cloudfront_distribution.artifact_cdn` | `frontend.tf` | Public CDN in front of the bucket. `GET`/`HEAD` only, gzip/brotli compression on, 5-minute default cache TTL, 1-hour max. Uses the shared `*.cloudfront.net` certificate — no custom domain wired up. |
| `aws_s3_bucket_policy.artifact_bucket_policy` | `frontend.tf` | Grants `s3:GetObject` to the CloudFront service principal, but only when the request comes from this specific distribution's ARN. |
| `aws_s3_object.index_html` | `frontend.tf` | Uploads `frontend/index.html` to the bucket root. Terraform tracks its MD5 hash, so re-running `apply` after editing the file re-uploads it automatically. |
| `aws_iam_role.scheduler_role` + `aws_iam_policy.scheduler_invoke_policy` | `scheduler.tf` | Lets EventBridge Scheduler call `lambda:InvokeFunction` — and only on this one function's ARN. |
| `aws_scheduler_schedule.daily_myths_agent` | `scheduler.tf` | The actual trigger: `cron(0 7 * * ? *)` in UTC, no flexible time window. That's 07:00 UTC, which is 08:00 in Lagos (WAT, UTC+1) year-round. |

## Access control

Two separate least-privilege IAM roles do all the work:

- **Lambda's role** can read/write objects in this one bucket, list it, write its own logs, and invoke exactly two Bedrock model ARNs. It cannot touch any other bucket or model.
- **Scheduler's role** can do exactly one thing: invoke this one Lambda function.

The bucket itself has no public access, no ACLs, and no policy allowing any principal to read it — except CloudFront, and only when the request's source ARN matches this distribution. That condition is what stops someone else from pointing their own CloudFront distribution at your bucket and serving your content from it.

## Deploying it

**Prerequisites**

- Terraform ≥ 1.14.0 and the AWS provider ≥ 6.0 (pinned in `version.tf`).
- An AWS account with Bedrock model access granted for `amazon.nova-lite-v1:0` and `amazon.nova-micro-v1:0` in `eu-north-1` (or whichever region you deploy to — update `provider.tf` if different).
- AWS credentials configured locally (`aws configure` or equivalent).

**1. Package the Lambda**

From the repository root:

```bash
zip lambda.zip lambda.py content_library.json
```

This has to produce `lambda.zip` one level above `infra/`, since `main.tf` references `"${path.module}/../lambda.zip"`.

**2. Deploy the infrastructure**

```bash
cd infra
terraform init
terraform validate
terraform fmt
terraform plan
terraform apply
```

This creates the bucket, the Lambda, the IAM roles, the CloudFront distribution, the schedule, and uploads `frontend/index.html` — all in one pass. The first `apply` also uploads whatever `BASE_URL` is currently hardcoded in `index.html`, which won't yet point at your new distribution.

**3. Point the frontend at its own CloudFront domain**

```bash
terraform output cloudfront_domain_name
```

Copy that value into the `BASE_URL` constant near the bottom of `frontend/index.html`, then re-apply so the updated file gets uploaded:

```bash
terraform apply
```

## Checking that it worked

Log into the AWS Console to check on the resources directly, or just open the CloudFront domain in a browser — the page should show a loading message briefly, then the day's card.

## Known limitations

Worth knowing before relying on this for anything beyond a personal project:

- **The manifest is a single read-append-write JSON file.** `update_manifest()` fetches the whole file, appends one entry, and writes it back. That's fine for one scheduled run a day, but two overlapping invocations (say, a manual test run colliding with the schedule) could overwrite each other's changes.
- **No custom domain or ACM certificate.** The site is only reachable at the default `*.cloudfront.net` address.
- **No dead-letter queue or alerting.** If Bedrock and its fallback both fail, or the S3 write fails, the only trace is whatever CloudWatch captures.

## Challenges encountered

**Model access is regional, and it isn't automatic.** Bedrock model access has to be explicitly granted per region before `InvokeModel`/`Converse` will work. The first model tried was actually Amazon Nova 2, which wasn't available in `eu-north-1` at the time — that's what pushed this project onto Nova Lite and Nova Micro (the v1 generation) instead, since those were the models actually enabled for this account in this region. The failure itself surfaced as an `AccessDeniedException` with no obvious hint that the fix was a model-access request in the console rather than an IAM change — the IAM policy was already correct.

**Deciding which errors deserve a fallback.** `generate_story()` only retries with Nova Micro for `ThrottlingException`, `ModelTimeoutException`, and `ServiceUnavailableException`. Early versions caught every `ClientError` and fell back unconditionally, which meant a genuine permissions problem or a bad request would silently retry against a second model and fail the same way twice, doubling the time to a useful error message in CloudWatch. Narrowing the except clause to specific error codes fixed that.

**Splitting the S3 IAM statements.** The first version of `lambda_access` granted `s3:PutObject`, `s3:GetObject`, and `s3:ListBucket` all under one `Resource: bucket-arn/*`. `ListBucket` actually needs to be granted on the bucket ARN itself, not on the objects inside it — an easy mistake that only shows up as an `AccessDenied` on `list_objects`/`head_bucket` calls, not on the reads and writes that get tested first. `main.tf` now has that as two separate statements with two different resource shapes.

**Being new to EventBridge Scheduler, Lambda, CloudWatch, and CloudFront.** All three were new services going into this project, and getting them wired together correctly — the Scheduler's own IAM role, the Lambda's execution role, and CloudFront's OAC and bucket policy all trusting the right principal — was a genuine hassle. Most of the early debugging time went into figuring out which of the three was actually rejecting a request, since a permissions failure in any one of them tends to look similar from the outside.

## What I learned

- **Lambda packaging** — how a plain zip with the handler and a supporting JSON file at the same level actually gets read at runtime.
- **Bedrock's Converse API** — a single, consistent request/response shape across different Nova model sizes, which is what makes a same-provider fallback (Lite → Micro) simple to write instead of needing separate handling per model.
- **IAM as something to actually scope, not just satisfy.** Writing `Resource` as a wildcard makes errors disappear immediately, which is exactly why it's tempting — and exactly why the two S3 statements and the two Bedrock model ARNs in `main.tf` are worth the extra lines.
- **EventBridge Scheduler as a distinct primitive from EventBridge rules** — a target ARN plus an execution role, rather than a rule pattern plus a resource-based permission on the target.
- **Origin Access Control** — why a bucket policy needs a source-ARN condition, not just a principal, to make sure only *your* CloudFront distribution can use the access it's been granted, and not anyone else's pointed at the same origin.
- **Keeping Terraform split by concern** — `main.tf` for compute and its own IAM, `frontend.tf` for the delivery layer, `scheduler.tf` for the trigger — made it much easier to reason about which file to open when something in one specific part of the pipeline broke.

## Possible next steps

1. Move the content library to DynamoDB, and track which pairings have already been used, so the story pool doesn't have to grow just to reduce repeats.
2. Add an explicit CloudWatch log group with a retention policy.
3. Introduce a wider range of technological concepts.
4. Attach a custom domain and ACM certificate to the CloudFront distribution.
5. Allow users to query the application, instead of only ever seeing a random daily pairing.

## Author

Built by **Human-Gechi**.

[![GitHub](https://img.shields.io/badge/GitHub-Human--Gechi-181717?logo=github&logoColor=white)](https://github.com/Human-Gechi)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-Ogechukwu%20Okoli-0A66C2?logo=linkedin&logoColor=white)](https://www.linkedin.com/in/ogechukwu-okoli-154684325)