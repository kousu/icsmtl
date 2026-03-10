## Bugs

- [x] mtlrave: if link in caption, include in ics; if not, use the telegram post link
- [x] mtlrave: trust the date from the TAG over the date from the OCR
- [ ] lowercase the titles/descriptions from ocr_flyer() (maybe only if they're entirely uppercase?)
- [ ] cultmtl: remove "The post ... first appeared on CultMTL"
- [ ] event de-duplicator
- [ ] consider embedding flyers into events via base64 URL encoding
- [ ] meetup: "The YD Hootenany" isn't being scraped
- [ ] preserve rich text in X-ALT-DESC;FMTTYPE=text/html field

## Sources

- [ ] https://www.effervescence-citoyenne.xyz/calendrier/
- [ ] https://ra.co/events/ca/montreal
- [ ] https://montreal.askapunk.net/
  - available direct at https://montreal.askapunk.net/feed/ics
- [ ] https://montreal.ca/evenements
- [x] https://www.meetup.com/yellowdoor/events/calendar
  - available direct at https://yellowdoor.org/feed/eo-events/
