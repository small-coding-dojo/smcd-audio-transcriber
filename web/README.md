# ClearVoice web UI (prototype)

React + TypeScript + Vite. The backend is **mocked in the browser** by default (`src/api/mock.ts`), so no service is needed.

```
npm install
npm run dev      # http://localhost:5173
npm test         # unit tests (formatting, exporters)
npm run build    # type-check + production build into dist/
```

Mock behaviour is driven by file name: `*fail*` → server error, `*silence*` → "no speech",
`*mono*` → no speaker labels, `*slow*` → 3× longer processing. Any real audio file works otherwise.

To use the real service: `VITE_API=real VITE_API_TARGET=http://localhost:8080 npm run dev`
(contract: `../docs/api-contract.md`).

Privacy: nothing is written to localStorage/cookies; the player uses a local object URL; CSP restricts connections to same origin.
