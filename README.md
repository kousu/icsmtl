ics scrapers

A collection of scrapers that convert common web sources into .ics files that can be shared.

## Install

```
git clone https://github.com/kousu/icsmtl
pip install --user --break-system-packages .  # python is overly precious; ~/.local is safe enough to install to
```

### Dev Install

Instead:

```
python -m venv .venv
. .venv/bin/activate
pip install -e .
```

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

You can then import calendar.ics into your local calendar app or Google Calendar or your phone (e.g. via [this](https://f-droid.org/en/packages/org.sufficientlysecure.ical/) or [etar](https://f-droid.org/en/packages/ws.xsoh.etar/) if you phone doesn't already do it natively)
