<p align="center"><img src="art/figure/steward.webp" width="600" alt="Steward: a dark rounded cube whose front is a 4x4 grid of lime cells, ten of them lit, with two glowing eyes"></p>

# Steward

A private, local-first operations brief for your Mac. Steward reads your disk once a day, says what changed and why, points at data that can safely be rebuilt, and never deletes anything on its own.

The character in the corner is the brief's voice. Its 4×4 grid is your real disk fill: ten lit cells means about 62 % used. It only says what the collector measured.

## What it does

- **Daily snapshot.** Directory sizes, project names and classification metadata. It never reads document contents.
- **Changes, explained.** What grew since the last reading, and where.
- **Reclaimable, honestly.** Only `safe`, `low` and `rebuildable` items count. Anything riskier is held for your review.
- **Learn.** A seven-day field guide (RAM against SSD storage, and so on). Every interactive model in it is labelled as an example, not live data.

Scheduled scans are read-only. Deletion never happens automatically.

## Run

```sh
npm run demo      # optional: copy demo data so the brief renders before your first reading
npm run collect   # take a reading (observation only)
npm run dev       # open http://127.0.0.1:4173
npm test
```

`npm run collect:safe` is the explicit cleanup path: it scans, clears only allowlisted caches and generated build outputs, records a receipt, and scans again. `node_modules`, app caches and Xcode archives are never cleared.

## Your data stays on your machine

The collector writes to `public/data/` and `data/snapshots/`, both gitignored. The repository ships demo data with the same schema in `demo/data/`. Snapshots older than 90 days are removed by the collector. The optional assistant sends a structurally redacted context to a cloud model only after you opt in per provider; with no key set, nothing leaves the machine.

## The figure

`art/figure/steward.py` builds the character in Blender from the same numbers as the CSS dock (48 px body, 4×4 cells inset 5 px, 9×13 px eyes set off the cell rhythm):

```sh
Blender --background --python-exit-code 1 --python art/figure/steward.py -- \
  --look a --engine cycles --samples 128 --res 1600 --fill 62 --out steward.png
```

## Licence

MIT. See [LICENSE](LICENSE).
