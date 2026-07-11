# NailSize AI

A web application that estimates a customer's nail dimensions from a calibrated photograph so nail artists can produce correctly sized press-on nails.

## Project status

The project is currently in product planning and technical design. Implementation will follow the requirements and task plan in [`outputs/plan.md`](outputs/plan.md) and [`outputs/task.md`](outputs/task.md).

## Intended deployment

- Web application hosted on Vercel
- Browser upload with server-side, ephemeral image processing
- No permanent storage of customer nail photographs
- Computer-vision sizing validated against a physical reference marker

## Development

Development commands will be documented here after the application scaffold is created. Do not commit secrets; use `.env.local` for local configuration and Vercel environment variables for deployed environments.
