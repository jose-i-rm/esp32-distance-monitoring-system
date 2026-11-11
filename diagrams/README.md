# Diagramas del sistema

Todos los diagramas están escritos en [Mermaid.js](https://mermaid.js.org/) y GitHub los renderiza automáticamente.

| # | Diagrama | Archivo |
|---|----------|---------|
| 1 | Arquitectura general | [01-arquitectura-general.md](./01-arquitectura-general.md) |
| 2 | Flujo de datos | [02-flujo-datos.md](./02-flujo-datos.md) |
| 3 | Conexión de hardware | [03-conexion-hardware.md](./03-conexion-hardware.md) |
| 4 | Flujo HTTP | [04-flujo-http.md](./04-flujo-http.md) |
| 5 | Pipeline de futuras integraciones IA | [05-pipeline-ia.md](./05-pipeline-ia.md) |
| 6 | Modelo de datos (ER) | [06-modelo-datos.md](./06-modelo-datos.md) |
| 7 | Arquitectura híbrida radar + cámara PTZ Tuya | [07-arquitectura-hibrida.md](./07-arquitectura-hibrida.md) |

Para exportarlos a PNG/SVG puede usar [Mermaid Live Editor](https://mermaid.live) o la CLI:

```bash
npm install -g @mermaid-js/mermaid-cli
mmdc -i 01-arquitectura-general.md -o arquitectura.svg
```
