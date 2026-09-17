# Fuentes y decisiones de versión

Consulta realizada el 17 de septiembre de 2026. Se priorizan releases, código y documentación oficial.

| Decisión | Fuente |
| --- | --- |
| Artículo que se actualiza | [LinkedIn, 26/12/2022](https://www.linkedin.com/pulse/vitess-o-como-escalar-con-mysql-de-manera-horizontal-abadia-lopez/) |
| Repositorio original | [pvtoCalvo/Vitess15Linkeding](https://github.com/pvtoCalvo/Vitess15Linkeding) |
| Última release estable consultada: v24.0.3, 03/09/2026 | [Release Vitess](https://github.com/vitessio/vitess/releases/tag/v24.0.3) |
| Operator v2.17.1, 03/09/2026 | [Release Operator](https://github.com/planetscale/vitess-operator/releases/tag/v2.17.1) |
| Compatibilidad Kubernetes de la versión fijada | [README del tag v2.17.1](https://github.com/planetscale/vitess-operator/blob/v2.17.1/README.md#compatibility) |
| Manifiestos, secretos y flujo de partida | [Ejemplos de v24.0.3](https://github.com/vitessio/vitess/tree/v24.0.3/examples/operator) |
| MySQL 8.0/8.4 y límites de soporte | [Bases de datos soportadas](https://vitess.io/docs/24.0/overview/supported-databases/) |
| La imagen lite predeterminada instala MySQL 8.4 | [Dockerfile v24.0.3](https://github.com/vitessio/vitess/blob/v24.0.3/docker/lite/Dockerfile) |
| Novedades de la serie 24 | [Anuncio Vitess 24](https://vitess.io/blog/2026-04-30-announcing-vitess-24/) |
| MoveTables, reglas y corte de tráfico | [Guía MoveTables](https://vitess.io/docs/24.0/user-guides/migration/move-tables/) |
| Sintaxis de Reshard | [Referencia Reshard](https://vitess.io/docs/24.0/reference/programs/vtctldclient/vtctldclient_reshard/) |
| Formato JSON exacto de VDiff | [vdiff.go, tag v24.0.3](https://github.com/vitessio/vitess/blob/v24.0.3/go/cmd/vtctldclient/command/vreplication/vdiff/vdiff.go) |
| Vindexes | [Referencia Vindexes](https://vitess.io/docs/24.0/reference/features/vindexes/) |
| Transición de CLI | [vtctldclient](https://vitess.io/docs/24.0/reference/vtctldclient/) |

Las etiquetas de contenedor se comprobaron mediante la API pública de Docker Hub: `vitess/lite:v24.0.3`, `vitess/vtadmin:v24.0.3` y `planetscale/vitess-operator:v2.17.1` ofrecían `linux/amd64`. Los tags son explícitos, aunque no se han fijado por digest. `versions.json` conserva el SHA-256 del manifiesto del operador original y de nuestra adaptación.

La página general de releases mostraba un parche anterior durante la consulta; para el parche actual se contrastó con la release de GitHub y su API. No se utiliza la documentación de v25 (desarrollo) como base del laboratorio.

Los manifiestos derivan del ejemplo upstream; se cambia el namespace a `vitess-lab`, se ajustan WATCH_NAMESPACE/RBAC, se declara el namespace del operador y se limita VTAdmin a lectura. `mysql80Compatible` es el nombre del campo de API del operador que usa el propio ejemplo; no indica que la imagen predeterminada contenga MySQL 8.0.
