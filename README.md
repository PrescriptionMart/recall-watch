# FDA Recall Watch

An internal tool for the Prescription Mart team. It checks the FDA's public drug recall data against a list of medications we watch, and flags anything new so pharmacists know they may get patient calls.

**Live page:** https://prescriptionmart.github.io/recall-watch/

## How it works

- Data comes from the FDA openFDA drug enforcement API (api.fda.gov), which is public government data.
- The watch list and the record of which recalls have already been reviewed are stored in your own browser on your own computer. They are not uploaded anywhere.
- No patient information of any kind is entered, stored, or transmitted by this page.

## How to use it

1. Open the live page.
2. Edit the watch list to match what we dispense. One medication per line, brand and generic on separate lines.
3. Click **Check FDA now**. Class I recalls (the most serious) sort to the top.
4. Anything not yet reviewed is marked **NEW**. Click **Mark all as seen** once reviewed so the next check only flags fresh items.
5. **Copy alert for pharmacists** puts a plain text summary on the clipboard to paste into a message.

## Notes

This page is informational. Confirm details on the official FDA recall notice before acting, and route clinical questions to a pharmacist.
