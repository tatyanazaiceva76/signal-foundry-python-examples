# Python CSV clients: website contacts, Greenhouse, Lever and Ashby jobs

Python 3.9+ clients for exporting source-linked company contacts or an employer hiring watchlist to a spreadsheet. A CSV batch driver handles website lists larger than one Actor input. Try the included synthetic JSON files before connecting an API. No package installation is needed.

**Publisher disclosure:** Signal Foundry publishes the paid Apify Actors used by the optional hosted modes below. These examples, tests and documentation were created with AI assistance. Downloading the code and running the offline samples does not start an Actor or require an Apify account.

Use the [website list to contact CSV guide](website-list-to-contact-csv.md) to start in the Apify web interface. It covers a capped trial on two pages, output with source links, offline conversion and larger website spreadsheets.

Have more than 25 website URLs? Start with the [offline CSV batch plan](#bulk-website-lists-from-csv), then authorize one aggregate Actor-run cap before hosted execution.

## Offline browser demo

Download **signal-foundry-csv-demo.html** from the [latest release](https://github.com/tatyanazaiceva76/signal-foundry-python-examples/releases/latest), then open that saved file in your browser. Try the built-in synthetic contacts or jobs, or choose your own JSON export and download a CSV. Conversion needs no Python, token, installation or network request. Files stay in the page; the demo has no analytics or remote scripts.

The demo accepts up to 2 MiB and 10,000 rows, keeps the contact and Greenhouse job columns, and offers a local email-only filter for contacts. Use the Python client below for Lever and Ashby records. The demo quotes CSV cells, adds a UTF-8 BOM and neutralizes formula-like strings with an apostrophe. The preview shortens long cells; the downloaded CSV keeps the full selected values. Preserve the original JSON for unmodified data. This demo converts existing exports; use the client instructions below for an optional paid hosted run.

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

## n8n: Greenhouse jobs to CSV

The [manual Greenhouse workflow](greenhouse-to-csv.n8n.json) uses only built-in **Manual Trigger → HTTP Request → Code → Convert to File** nodes. Download its raw JSON and use **Import from File**, or **Import from URL** with:

```text
https://raw.githubusercontent.com/tatyanazaiceva76/signal-foundry-python-examples/main/greenhouse-to-csv.n8n.json
```

1. On **Get Greenhouse jobs — max $0.02**, select a private **Header Auth** credential: header `Authorization`, value `Bearer YOUR_APIFY_TOKEN`. The shared workflow contains no token or credential ID; importing it does not start a run.
2. Edit the node's **JSON body**: `boardTokens` selects explicit employers; `titleContains`, `descriptionContains`, `locationContains` and `departmentContains` accept case-insensitive substrings. Supplied filters combine as AND conditions before delivery and charging. The example asks for engineering roles mentioning Python on the `anthropic` board; current matches are not guaranteed.
3. Review the Actor's current price and execute manually. This starts one paid snapshot, scans at most 1,000 listings and delivers at most ten job versions, with a **$0.02 server-side cap**. At the base price ten rows cost **$0.015**, including platform usage. A cap does not guarantee ten matches; zero matches have no result charge.
4. Download binary field `data` from **Create jobs.csv**. It keeps company, title, displayed location, departments, public source dates, job URL and description text. Formula-like cells receive an apostrophe prefix; retain the original JSON for unchanged strings. An empty dataset may produce no CSV file.

The workflow is inactive, uses no community nodes, creates no schedule and sends no mail or applicant data. Automatic retries are disabled. If a response is interrupted, inspect the existing run in Apify Console before another execution: the first paid POST may already have started work.

For sequential repeat checks, optionally set `onlyNew: true` and use one stable `stateKey` per combination of boards, filters and description setting. The first check can deliver existing matches. History retains up to 25,000 fingerprints; older versions may reappear. This Actor does not emit closed-job events, discover every employer or infer salary, visa sponsorship or remote eligibility.

The workflow JSON and its transformation code were checked locally with synthetic job rows, malformed responses, empty input and spreadsheet formula cases. **Live import and execution in n8n have not been verified.** The backend was previously validated separately; that is not a live workflow test or customer payment. Publisher ownership and AI assistance are disclosed above. [Actor details and limits](https://apify.com/signalfoundryhq/greenhouse-hiring-radar).

## Start offline

Download this repository with GitHub's **Code → Download ZIP**, or clone it:

```bash
git clone https://github.com/tatyanazaiceva76/signal-foundry-python-examples.git
cd signal-foundry-python-examples
python3 export_contacts.py --from-json sample_contacts.json --output contacts.csv
python3 export_jobs.py --from-json sample_jobs.json --output jobs.csv
python3 export_ats_jobs.py --provider lever --from-json sample_lever_jobs.json --output jobs.csv
python3 export_ats_jobs.py --provider ashby --from-json sample_ashby_jobs.json --output jobs.csv
```

Each command writes two synthetic rows. The datasets use the reserved `example.com` domain: they are demonstration records, not collected leads or current vacancies. These commands need no token, network request or paid run.

## Choose the hosted tool

| Need | Client | Paid backend | Default run cap |
| --- | --- | --- | --- |
| Published emails, phone links and social profiles from a known website list | `export_contacts.py` | [Website Contact Scraper](https://apify.com/signalfoundryhq/website-contact-extractor) | $0.03 |
| Public job versions from explicit Greenhouse employer boards, with description text | `export_jobs.py` | [Greenhouse Jobs Scraper](https://apify.com/signalfoundryhq/greenhouse-hiring-radar) | $0.02 |
| Public Lever job metadata, including global and EU boards | `export_ats_jobs.py --provider lever` | [Lever Jobs Scraper](https://apify.com/signalfoundryhq/lever-hiring-radar) | $0.02 |
| Listed Ashby job metadata and employer-disclosed compensation | `export_ats_jobs.py --provider ashby` | [Ashby Jobs Scraper](https://apify.com/signalfoundryhq/ashby-hiring-radar) | $0.02 |

Hosted mode requires an Apify account and your own API token in the `APIFY_TOKEN` environment variable. Each command starts one new Actor run. A charge cap limits that run's charge; it does not guarantee a number of results. Review the linked Actor's current pricing before execution.

## Lever and Ashby jobs to CSV

Use `export_ats_jobs.py` with `export_jobs.py` in the same folder, or clone this repository. The shared helper needs only the Python standard library. The two `--from-json` commands above each convert two **synthetic** normalized Actor records without a token, network request or paid run. They overwrite the named CSV; choose a different `--output` to keep separate exports. Sample URLs use `example.com`; sample compensation is invented for format testing and is not salary research.

For a hosted run, create `boards.txt` with one employer board token or HTTPS board URL per line. Use a separate file for each provider:

| Provider | Accepted board examples | Source scope |
| --- | --- | --- |
| Lever | `spotify`, `eu:YOUR_BOARD`, `https://jobs.eu.lever.co/YOUR_BOARD` | Public global or EU-hosted Lever boards. Keep token case as shown by the source. |
| Ashby | `linear`, `https://jobs.ashbyhq.com/YOUR_BOARD` | Listed public Ashby jobs only. Compensation is included when the employer exposes it. |

`YOUR_BOARD` is a placeholder, not a working company. Use the employer's board URL rather than a single job or application link. The client rejects other hosts, credentials, URL query parameters and mixed-provider boards before an API request. Each run accepts at most 25 boards; it does not find employers automatically.

Set your own `APIFY_TOKEN` privately, review the current Actor price, then choose **one** provider command:

```bash
python3 export_ats_jobs.py --provider lever --boards boards.txt --title-contains engineer --max-items 10 --max-charge 0.02 --output jobs.csv
# For a separate Ashby board list instead:
python3 export_ats_jobs.py --provider ashby --boards boards.txt --title-contains engineer --max-items 10 --max-charge 0.02 --output jobs.csv
```

Each command makes **one new paid POST**, with a **$0.02 server-side run cap**, at most ten delivered job versions and 1,000 source records scanned by default. Executing both starts two separately capped runs; this client has no aggregate budget manager. Each backend's base price is **$0.0015 per delivered job metadata version ($1.50 per 1,000)**, including platform usage, with no start fee. Ten rows cost $0.015 at that price. A cap does not promise ten matches or complete coverage. Filters `--title-contains`, `--location-contains` and `--department-contains` are case-insensitive substrings combined as AND conditions before delivery and result charging.

The UTF-8 CSV includes `provider`, source board and job IDs, title, locations, department, team, employment/workplace types, job/apply/API URLs and `signalId`. Lever `createdAt` and Ashby `publishedAt` stay in **separate columns**: creation and last publication are different dates. Missing values stay empty. `salaryRangeJson`, `compensationJson` and `secondaryLocationsJson` retain the source objects, including currency and interval, without annualizing or guessing compensation. CSV quoting, a UTF-8 BOM and formula-cell prefixes help spreadsheet import; keep the original JSON for unchanged strings. This converter accepts the linked Actors' normalized dataset arrays, not raw Lever or Ashby API envelopes.

For a repeat feed, add `--only-new`. The default history key is derived from provider, ordered boards, filters and compensation setting. Keep them stable to skip remembered delivered versions. The first check can return existing jobs; the backend retains at most 25,000 fingerprints, and older versions may reappear after eviction. Optional `--state-key` selects an explicit feed history. Neither backend emits closed-job/deletion events or full job descriptions. Ashby remote flags and compensation are reported only when supplied; the client does not infer remote eligibility, visa support or salary.

No automatic retry or redirect is used for the paid POST. If it times out, inspect that Actor's existing runs in Apify Console and export the already-created dataset before starting another. To convert it without another run:

```bash
python3 export_ats_jobs.py --provider lever --from-json existing-dataset.json --output jobs.csv
```

Use `--provider ashby` for an Ashby dataset. Empty datasets produce a header-only CSV. No schedule, Google Sheets authorization, applicant submission, email or community node is created. The client and synthetic cases were tested locally; **this new client has not executed a live paid run**. Signal Foundry publishes the optional paid backends and prepared this implementation and documentation with AI assistance.

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

## Bulk website lists from CSV

Use [batch_contacts.py](batch_contacts.py) with `export_contacts.py` in the same folder. It reads one selected website column from a UTF-8 CSV, removes identical normalized starting URLs, splits the list into batches of at most 25 and combines the returned page records into one CSV. Other input columns are not submitted to Apify or carried into the output; keep the original file for joins by website. Different paths on one domain remain separate starting URLs.

Start with the included **synthetic** file. Its `.example` hosts are placeholders, not businesses or an extraction target:

```bash
python3 batch_contacts.py --input-csv sample_websites.csv
```

This performs **no network request**, needs no token, starts no run and creates no checkpoint or output. The sample has 61 input rows, 60 unique URLs and 3 batches. With the default **$0.08 cap per batch**, the sum of run caps is **$0.24**. That is a ceiling, not a price quote or an invoice.

For your own data, put a `website` header in `my-websites.csv`, or select another exact header with `--column Website`. Review the current [Actor price and limits](https://apify.com/signalfoundryhq/website-contact-extractor), set your own `APIFY_TOKEN`, and opt in explicitly:

```bash
python3 batch_contacts.py --input-csv my-websites.csv --require-email --batch-cap 0.08 --max-total-charge 0.24 --execute --output contacts.csv
```

That example authorizes at most three $0.08 runs; if the CSV needs more batches, it stops **before any API call**. Set the total only after reviewing the offline plan. The program requires the sum of every planned batch cap to fit inside the authorized total, and does not recycle unused or provisional charges. The bound applies to new Actor runs in this one unchanged checkpoint, not to unrelated account activity or separately billed storage/API usage. Larger `--max-pages` values can require a higher per-run cap; a cap may truncate results and never guarantees a match or complete site coverage.

The default scans one starting page per website. `--require-email` filters no-email page records before delivery and result charging; it does not verify mailboxes. The base Actor price remains **$0.003 per delivered page version**, including its platform usage, with no start fee and plan discounts where listed. One page row can include several contacts. This helper does not scrape Google Maps, find private employee emails, send messages or create a schedule.

A private checkpoint at `.private/contact-batch-state.json` stores the plan, original run IDs and completed results, **never the API token**. Keep it private: run and dataset IDs can provide data access. A lock prevents simultaneous processes using the same checkpoint. Completed batches are reused, and a saved live run is inspected rather than recreated. Resume with the same input and settings:

```bash
python3 batch_contacts.py --input-csv my-websites.csv --require-email --batch-cap 0.08 --max-total-charge 0.24 --execute --resume --output contacts.csv
```

If a start response was lost before its run ID was saved, this command stops. Find that exact run in Apify Console, then add `--recover-run RUN_ID` to the resume command. Recovery checks the Actor, server charge cap and saved run input before adopting the ID. If you cannot establish the outcome, do not start a replacement. Do not edit or delete a checkpoint to retry the same job. A hard process kill can leave a `.lock` file; remove that file only after confirming the original process has exited. A failed batch stops further starts; any completed CSV and checkpoint data remain available.

**Validation on 26 October 2026:** nine focused offline tests cover batch merging, aggregate caps, durable run IDs, ambiguous starts, input-checked recovery and concurrent-use rejection. A separate owner check completed two one-website batches on the Python help and Django foundation contact pages, with a combined configured run cap of **$0.006** and email-only output. It returned one combined page record; a subsequent recovery check read the existing run and input without a new POST. These are owner tests, not customer work or proof of sales. The sixty-URL test uses synthetic responses; it is not a live sixty-site benchmark.

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

All `--from-json` commands work with an existing JSON array downloaded from the corresponding Actor. They do not create new runs. Offline conversion cannot change charges from the original run. The jobs clients convert the supplied rows; their source filters and history flags apply only to hosted board requests.

The exporters write UTF-8 CSV with a BOM and quoted cells. Formula-like strings receive a leading apostrophe, which changes the exported string; retain the original JSON for unmodified processing and import untrusted spreadsheet columns as text. Descriptions can contain line breaks inside a quoted CSV cell.

## If a hosted request is interrupted

The clients do not automatically retry paid POSTs. Check the Actor's recent runs in Apify Console and retrieve the existing dataset before repeating a command: an interrupted response can hide a run that already started. Hosted calls use a 120-second Actor timeout and a 150-second HTTP timeout. For larger jobs, use the [asynchronous run API](https://docs.apify.com/api/v2/actor-run-post).

Do not put tokens in command URLs, shared JSON or issue reports. The clients send the token in the HTTPS Authorization header. This repository contains no token or captured customer data.

## Run the local tests

```bash
python3 -m unittest discover -p 'test_*.py' -v
```

The tests cover offline conversion, CSV output, charge-cap and authentication placement, no automatic paid-POST retries, and jobs feed history keys. Network calls in the tests are mocked. The published client versions were also checked against their original files; a separate capped owner run validated the original Greenhouse integration. The new Lever/Ashby client has only local mocked and synthetic validation. Owner tests are not customer usage or sales evidence.

## Scope and support

These are independent integrations, not affiliated with Greenhouse, Lever, Ashby or the employers. Source website and job-description content remains subject to the relevant provider and publisher rights; these examples do not grant a separate licence to that source content. The included sample datasets are synthetic.

Report a reproducible hosted-tool problem through the corresponding Actor's Apify Issues tab. Include the run ID and filters, never an API token or private contact data.
