# Dashboard Big Data

Dashboard web para monitorear los eventos, productos, regiones, audiencias y alertas del proyecto de Big Data.

## Development

Necesitas Node.js y npm, o Bun si prefieres usar el lockfile incluido.

```sh
npm i
npm run dev
```

Con Bun:

```sh
bun install
bun run dev
```

## Modo conectado

El dashboard puede consumir el backend realtime en `http://localhost:8000`.

```sh
cp .env.example .env
bun run dev
```

Desde la raiz del monorepo tambien puedes usar:

```sh
make setup-d
make backend-d
make dashboard-d
```

## Built with

- TanStack Start
- TypeScript
- React
- Tailwind CSS
