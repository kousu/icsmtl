ics scrapers

A collection of scrapers that convert common web sources into .ics files that can be shared.

## Examples

```
mtlrave-telegram --start 2025-11-01 --end 2026-04-30 # https://t.me/s/mtlrave        => events/mtlrave_telegram/*.ics
cultmtl                                              # https://cultmtl.com/events    => events/cultmtl/*.ics
meetup yellowdoor                                    # https://meetup.com/yellowdoor => events/meetup/yellowdoor/*.ics
```


Helper to put everything into one package:

```
catics events/**/*.ics > calendar.ics
```
