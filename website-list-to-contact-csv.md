# Extract public contact emails from a website list into CSV

**Publisher disclosure:** Signal Foundry publishes the paid Website Contact Scraper used in this walkthrough. Gleb Zaitsev operates this project. This article and the integration code were created with AI assistance. The examples below distinguish synthetic data from an owner test.

You already have a spreadsheet of company websites and want a contact CSV with a source link beside each result. The useful first step is a small extraction you can inspect: two websites, one page per website and a charge ceiling. An LLM key is not required for this workflow.

## Choose the starting point that matches your file

| What you have | Starting point | Cost boundary |
| --- | --- | --- |
| Public website or contact-page URLs | The hosted Actor in Apify Console | Paid extraction; set a maximum run charge |
| An existing contact JSON export | The local browser demo or Python converter | Conversion starts no new Actor run; it cannot reverse an earlier charge |
| A CSV with a website column and more than 25 URLs | The Python batch client | Explicit execution, per-batch caps and a total bound for its planned Actor runs |

## Start with two known contact pages

Open the [Website Contact Scraper, including current pricing and input](https://apify.com/signalfoundryhq/website-contact-extractor?utm_source=github&utm_medium=repository_guide&utm_campaign=public_contacts_csv_20261026). Hosted extraction requires an Apify account. Use the JSON input below, or enter the same values in the input form:

```json
{
  "websiteUrls": [
    "https://www.python.org/about/help/",
    "https://www.djangoproject.com/contact/foundation/"
  ],
  "maxPagesPerSite": 1,
  "maxItems": 2,
  "requireEmail": true,
  "onlyNew": false
}
```

Before starting, set the run's maximum charge to **US$0.006** and review the price shown for your account. At the base price of **US$0.003 per delivered page version**, two delivered records fit inside that ceiling. Eligible Apify plans have lower event prices. Platform usage is included in this Actor price and there is no Actor start fee.

A charge ceiling is not an invoice or a promise of two results. It can truncate a run. The default above reads only the starting page on each website. Increasing the crawl depth changes the work and possible output, so review the settings before reusing a budget.

## Understand which page records are delivered

`requireEmail: true` makes the Actor omit pages without extracted email before delivery and result charging. It does not test whether a mailbox exists. With the option off, a delivered page record may contain only phone links or social profiles.

Billing is per delivered *page version*, not per email address. One row can hold several emails from the same source page. `onlyNew: false` requests a snapshot: another run can deliver and charge for those records again.

This workflow reads published HTML. Contact forms, JavaScript-only details, robots rules and access restrictions can prevent extraction. Use public pages you are entitled to process. A published address does not establish permission to send it marketing messages.

## Keep the source beside the extracted details

When the run succeeds, inspect its dataset before downloading a CSV. The contact columns are `websiteUrl`, `pageUrl`, `pageTitle`, `emails`, `phones` and `socialLinks`. A row with its source link lets you check the actual page rather than treating an extracted string as a verified lead.

The supplied local converters join multiple contacts into semicolon-separated cells. They write UTF-8 CSV with a BOM and prefix formula-like values with an apostrophe. That changes the cell text, including some phone numbers beginning with `+`. Retain the original JSON and import untrusted spreadsheet columns as text.

**Synthetic format example:** the reserved `.example` domains below are placeholders. This row is not a business, a customer result or a target to scrape.

```csv
websiteUrl,pageUrl,pageTitle,emails,phones,socialLinks
https://acme.example,https://acme.example/contact,Contact,hello@acme.example;sales@acme.example,,
```

## Convert an export without another extraction

If you already downloaded the matching contact dataset as JSON, start with the [instructions for the local browser demo](https://gist.github.com/tatyanazaiceva76/b5aafad7a3b5dd35f7d32c001e195a22#try-it-in-a-browser). Save and open the provided HTML demo locally, choose the contact mode, then load the JSON and export a CSV. The demo processes files in your browser, sends no data to a server and includes no analytics. Its limits are 2 MiB and 10,000 rows.

For Python 3.9+, the same guide supplies the standard-library converter:

```bash
python3 export_contacts.py --from-json contacts.json --output contacts.csv
```

This conversion needs no API token and starts no run. It changes the file format, not the charges or coverage of the extraction that produced the JSON.

## Process a larger website spreadsheet

The [batch client and complete execution guide](https://github.com/tatyanazaiceva76/signal-foundry-python-examples#bulk-website-lists-from-csv) read one selected CSV column, remove identical normalized starting URLs, split the list into batches of at most 25 and combine returned page records into one CSV. Keep `batch_contacts.py` and `export_contacts.py` from that repository together.

Start with the included synthetic website file:

```bash
python3 batch_contacts.py --input-csv sample_websites.csv
```

The default produces an offline plan: no token, network request, Actor run, checkpoint or output file. The sample contains 61 rows and 60 unique placeholder URLs. It plans three batches; the default US$0.08 cap for each gives a US$0.24 sum of caps. That is a configured ceiling, not a quote for processing your websites.

For your real list, review the plan before choosing `--execute` and `--max-total-charge`. The sum of every planned batch cap must fit within that total. The bound applies to Actor runs in one unchanged checkpoint; unrelated account activity and separately billed storage or API usage are outside it. Other CSV columns are not submitted to Apify or copied into the result, so retain your original spreadsheet for joins.

The client saves known run IDs in a private checkpoint. It can resume an existing run or reuse completed results. If a start response is lost before the ID is saved, it stops for reconciliation. Follow the guide to identify the original run; creating a replacement immediately can cause a second charge. Do not share your token, checkpoint, run IDs or private contact data in a public support thread.

## Owner validation on 26 October 2026

On **26 October 2026**, an owner check processed the two real URLs above as two separate batches with one website each. Each had a US$0.003 run cap, for a US$0.006 combined ceiling. Both runs succeeded. The email-only output contained one Python help-page record and no Django foundation-page record. Source pages can change.

This was our own product QA, not work for a paying customer. It is not a general email coverage rate. The separate 60-URL batch test used synthetic responses. The published client suite passed 24 local tests, including capped batching, ambiguous-start handling and resuming known runs.

For a first trial, inspect a small result and its source page before increasing the list. Use the [Actor's current price, full guide and Issues tab](https://apify.com/signalfoundryhq/website-contact-extractor?utm_source=github&utm_medium=repository_guide&utm_campaign=public_contacts_csv_20261026) for hosted extraction, and the linked public client guide for offline conversion and batch recovery.
