# Python CSV clients: website contacts and Greenhouse jobs

Two standalone Python 3.9+ examples for exporting source-linked company contacts or an employer hiring watchlist to a spreadsheet. Try both with the included synthetic JSON files before connecting an API. No package installation is needed.

**Publisher disclosure:** Signal Foundry publishes the paid Apify Actors used by the optional hosted modes below. These examples, tests and documentation were created with AI assistance. Downloading the code and running the offline samples does not start an Actor or require an Apify account.

## Offline browser demo

Download **signal-foundry-csv-demo.html** from the [latest release](https://github.com/tatyanazaiceva76/signal-foundry-python-examples/releases/latest), then open that saved file in your browser. Try the built-in synthetic contacts or jobs, or choose your own JSON export and download a CSV. Conversion needs no Python, token, installation or network request. Files stay in the page; the demo has no analytics or remote scripts.

The demo accepts up to 2 MiB and 10,000 rows, keeps the same contact/job columns as the Python clients, and offers a local email-only filter for contacts. It quotes CSV cells, adds a UTF-8 BOM and neutralizes formula-like strings with an apostrophe. The preview shortens long cells; the downloaded CSV keeps the full selected values. Preserve the original JSON for unmodified data. This demo converts existing exports; use the client instructions below for an optional paid hosted run.

## Agent skill

[Source-linked website contacts to CSV](skills/apify-source-linked-contacts-csv/SKILL.md) packages the contact workflow for compatible AI coding assistants. It includes its own Python helper and synthetic offline sample. Hosted requests require the user's authorized spending cap; installing or reading the skill does not start an Actor. The skill is self-contained under `skills/apify-source-linked-contacts-csv/`.

## n8n: website contacts to CSV

The [importable n8n workflow](contacts-to-csv.n8n.json) connects **Manual Trigger → HTTP Request → Code → Convert to File**. Download the JSON using GitHub's **Raw → Download raw file**, then choose **Import from File** in n8n. Alternatively, use **Import from URL** with:

```text
https://raw.githubusercontent.com/tatyanazaiceva76/signal-foundry-python-examples/main/contacts-to-csv.n8n.json
```

The workflow is inactive and contains no token, credential ID or captured contact data. Importing it does not start a run. To configure it:

1. On **Extract contacts — max $0.03**, select a private **Header Auth** credential: header name `Authorization`, value `Bearer YOUR_APIFY_TOKEN`, using your own Apify token. Keep it out of the shared workflow JSON and URL.
2. Edit `websiteUrls` in that node's **JSON body**. The example uses two public project contact pages; replace them with the pages you intend to process. Keep numbers and booleans typed as JSON values.
3. Review the input and the Actor's current price, then execute manually. One execution starts one paid snapshot, with a **$0.03 server-side cap**, at most ten delivered rows and one starting page per site. `requireEmail: true` filters no-email pages before delivery and result charging. It does not verify a mailbox or grant permission to contact anyone.
4. Download binary field `data` from **Create contacts.csv**. Output preserves website and page sources and joins contact arrays into cells. Formula-like strings receive an apostrophe prefix; retain the JSON for unmodified data.

Automatic retries are disabled. A timeout can hide a run that already started: inspect the Actor's recent runs in Apify Console and retrieve that existing dataset before repeating the POST. Empty results may produce no CSV file. This manual workflow creates no schedule, mail campaign or Google Sheets connection.

The unchanged template was checked locally against the HTTP Request 4.2, Code 2 and Convert to File 1.1 node definitions, including normal, empty, malformed and formula-like rows. **Import and execution in a live n8n instance have not been verified.** The [Actor guide](https://apify.com/signalfoundryhq/website-contact-extractor) includes a manual node-by-node recipe. Publisher ownership and AI assistance are disclosed above; this is an independent integration, not an n8n endorsement.

## Start offline

Download this repository with GitHub's **Code → Download ZIP**, or clone it:

```bash
git clone https://github.com/tatyanazaiceva76/signal-foundry-python-examples.git
cd signal-foundry-python-examples
python3 export_contacts.py --from-json sample_contacts.json --output contacts.csv
python3 export_jobs.py --from-json sample_jobs.json --output jobs.csv
```

Each command writes two synthetic rows. The datasets use the reserved `example.com` domain: they are demonstration records, not collected leads or current vacancies. These commands need no token, network request or paid run.

## Choose the hosted tool

| Need | Client | Paid backend | Default run cap |
| --- | --- | --- | --- |
| Published emails, phone links and social profiles from a known website list | `export_contacts.py` | [Website Contact Scraper](https://apify.com/signalfoundryhq/website-contact-extractor) | $0.03 |
| Public job versions from explicit Greenhouse employer boards, with description text | `export_jobs.py` | [Greenhouse Jobs Scraper](https://apify.com/signalfoundryhq/greenhouse-hiring-radar) | $0.02 |

Hosted mode requires an Apify account and your own API token in the `APIFY_TOKEN` environment variable. Each command starts one new Actor run. A charge cap limits that run's charge; it does not guarantee a number of results. Review the linked Actor's current pricing before execution.

## Website contacts to CSV

Put one public domain or contact-page URL per line in `sites.txt`, for example:

```text
www.python.org/about/help/
https://www.djangoproject.com/contact/foundation/
```

After setting your own `APIFY_TOKEN`, run:

```bash
python3 export_contacts.py --websites sites.txt --require-email --max-pages 1 --max-items 10 --max-charge 0.03 --output contacts.csv
```

This is a paid hosted run. The base price is **$0.003 per delivered page version ($3 per 1,000)**, including platform usage, with no Actor start fee. Eligible Apify plans have lower event prices. A page row can hold multiple contacts; billing is per delivered row, not per email address.

`--require-email` asks the Actor to omit pages without extracted email **before delivery and result charging**. It checks that an email was extracted, not whether a mailbox exists or whether its owner has consented to receive messages. JavaScript-only pages and access restrictions can prevent extraction. `--max-pages 1` examines the starting page only.

The CSV columns are `websiteUrl`, `pageUrl`, `pageTitle`, `emails`, `phones` and `socialLinks`. Arrays are joined into semicolon-separated cells; source URLs stay in the output.

[Complete contact-client guide and standalone files](https://gist.github.com/tatyanazaiceva76/b5aafad7a3b5dd35f7d32c001e195a22).

## Greenhouse jobs to CSV

Put one Greenhouse board token per line in `boards.txt`, for example:

```text
anthropic
```

Then run:

```bash
python3 export_jobs.py --boards boards.txt --title-contains engineer --description-contains python --max-items 10 --max-scanned 1000 --max-charge 0.02 --output jobs.csv
```

This is a paid hosted run. The base price is **$0.0015 per delivered job version ($1.50 per 1,000)**, including platform usage, with no Actor start fee. Ten rows cost $0.015 at that base rate. Eligible Apify plans have lower prices.

The Actor reads explicit employer boards. It does not discover every Greenhouse customer or search a global jobs database. Title, location and description filters are case-insensitive substrings; supplied filters combine as AND conditions before delivery and charging. This client enables public description text in its output. It does not infer salary, visa sponsorship or remote eligibility.

Add `--only-new` to skip job versions already delivered for the same feed. The script derives a history key from the boards and filters. The first run can deliver all current matches; later runs skip remembered versions. History is bounded to 25,000 fingerprints, and removed jobs are not emitted as closed-job events. No schedule or notification is created.

[Complete jobs-client guide and standalone files](https://gist.github.com/tatyanazaiceva76/de9736e4472fb6ae9cdead5c624335aa).

## Reuse an existing dataset

Both `--from-json` commands work with an existing JSON array downloaded from the corresponding Actor. They do not create new runs. Offline conversion cannot change charges from the original run. The jobs client converts the supplied rows unchanged; its source filters and history flags apply only to hosted board requests.

Both exporters write UTF-8 CSV with a BOM and quoted cells. Formula-like strings receive a leading apostrophe, which changes the exported string; retain the original JSON for unmodified processing and import untrusted spreadsheet columns as text. Descriptions can contain line breaks inside a quoted CSV cell.

## If a hosted request is interrupted

The clients do not automatically retry paid POSTs. Check the Actor's recent runs in Apify Console and retrieve the existing dataset before repeating a command: an interrupted response can hide a run that already started. Hosted calls use a 120-second Actor timeout and a 150-second HTTP timeout. For larger jobs, use the [asynchronous run API](https://docs.apify.com/api/v2/actor-run-post).

Do not put tokens in command URLs, shared JSON or issue reports. The clients send the token in the HTTPS Authorization header. This repository contains no token or captured customer data.

## Run the local tests

```bash
python3 -m unittest discover -p 'test_export_*.py' -v
```

The tests cover offline conversion, CSV output, charge-cap and authentication placement, no automatic paid-POST retries, and jobs feed history keys. Network calls in the tests are mocked. The published client versions were also checked against their original files; a separate capped owner run validated the jobs integration. Owner tests are not customer usage or sales evidence.

## Scope and support

These are independent integrations, not affiliated with Greenhouse or the employers. Source website and job-description content remains subject to the relevant provider and publisher rights; these examples do not grant a separate licence to that source content. The included sample datasets are synthetic.

Report a reproducible hosted-tool problem through the corresponding Actor's Apify Issues tab. Include the run ID and filters, never an API token or private contact data.
