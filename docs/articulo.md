# Vitess en 2026: cómo escalar MySQL horizontalmente y comprobar que tus datos llegan al otro lado

*Cristo Fernando Abadia Lopez · actualización del 17 de septiembre de 2026*

Buenas, gente del IT.

En diciembre de 2022 publiqué un artículo sobre cómo empezar con Vitess. La idea sigue siendo útil: repartir datos y trabajo entre varios MySQL cuando una única instancia se queda pequeña. Pero el ecosistema ha cambiado y aquel laboratorio utilizaba Vitess 15, comandos antiguos y una configuración de Kubernetes que merece una revisión.

Esta actualización incluye un [repositorio con el artículo y el código](https://github.com/pvtoCalvo/vitess-mysql-sharding-lab). El recorrido parte de una pequeña tienda: productos, clientes y pedidos. Primero separaremos tablas; después fragmentaremos las filas de clientes y pedidos. Usaremos datos desde el principio para poder comprobar qué estamos moviendo.

## Las versiones de este ejemplo

A fecha de consulta, las últimas releases estables publicadas son **Vitess 24.0.3** y **Vitess Operator 2.17.1**, ambas del 3 de septiembre de 2026. El laboratorio fija esas versiones y Kubernetes **1.35.0**, dentro del rango de compatibilidad del operador. La elección del parche de Kubernetes busca una base explícita para el ejercicio; para producción hay que revisar también sus actualizaciones de seguridad. [Vitess](https://github.com/vitessio/vitess/releases/tag/v24.0.3), [Operator](https://github.com/planetscale/vitess-operator/releases/tag/v2.17.1), [matriz del tag utilizado](https://github.com/planetscale/vitess-operator/blob/v2.17.1/README.md#compatibility).

Vitess 24 incorpora mejoras como logging estructurado, integración con OpenTelemetry y más posibilidades para ejecutar determinadas consultas sobre shards. La compatibilidad SQL depende de la consulta y del esquema de distribución: no basta con cambiar el endpoint y asumir que todo tendrá el mismo comportamiento. [Anuncio de Vitess 24](https://vitess.io/blog/2026-04-30-announcing-vitess-24/).

La serie 24 soporta MySQL 8.0 y 8.4; la documentación anuncia que será la última serie con soporte para 8.0. La imagen `lite` predeterminada que utilizamos se construye con MySQL 8.4. [Soporte de bases de datos](https://vitess.io/docs/24.0/overview/supported-databases/), [Dockerfile fijado](https://github.com/vitessio/vitess/blob/v24.0.3/docker/lite/Dockerfile).

## Replicar y fragmentar resuelven problemas diferentes

Una réplica conserva una copia de datos de su origen. Puede ayudar a servir lecturas y a diseñar alta disponibilidad. Eso no divide automáticamente la carga de escritura ni el volumen de datos de ese origen entre varios servidores.

Con sharding horizontal, distintas filas pertenecen a distintos shards. Si el acceso acompaña esa distribución, se puede repartir almacenamiento y trabajo. El resultado depende de la carga: una consulta que termina visitando todos los shards puede seguir siendo cara.

También conviene matizar el uso de «vertical». En diseño de datos puede referirse a separar columnas, pero en este recorrido con Vitess separaremos **tablas completas entre keyspaces** mediante MoveTables. Después, Reshard distribuirá filas dentro del keyspace elegido.

No hace falta fragmentar cualquier base de datos. Primero merece la pena entender sus consultas, índices, tamaño de trabajo, contención y capacidad disponible. Vitess añade herramientas potentes y también una nueva responsabilidad operativa.

## Qué hay detrás de la conexión MySQL

La aplicación se conecta a **VTGate**. Este interpreta y planifica SQL, consulta el VSchema y decide a qué tablets enviar el trabajo. Es más que un balanceador TCP.

Cada **VTTablet** administra una instancia MySQL y participa en la ejecución de consultas. Un **shard** representa una parte del espacio de datos; normalmente tiene un primary y réplicas. El **keyspace** es la agrupación lógica que la aplicación utiliza como base de datos.

El servicio de topología mantiene metadatos del clúster. **VTOrc** interviene en la detección y recuperación de fallos; **vtctld** expone operaciones de administración; **vtctldclient** es la herramienta de línea de comandos que utilizaremos. **VTAdmin** aporta una interfaz de inspección.

Una **cell** agrupa infraestructura según la topología y los dominios de fallo definidos. Añadir otra cell no crea por sí solo una estrategia completa de recuperación regional: hay que diseñar dónde están los datos, cómo replican y cómo cambia el tráfico.

## Elegir la clave de fragmentación es una decisión de aplicación

Nuestro ejemplo usa `customer_id` para distribuir tanto `customer` como `corder`. Eso permite colocar a un cliente y sus pedidos en el mismo shard. Una consulta que identifica ese cliente puede aprovechar el enrutamiento dirigido.

El **primary vindex** transforma el valor de una columna en un identificador que permite localizar su shard. En este caso usamos `hash`; no todos los tipos de vindex tienen las mismas propiedades. Un vindex tampoco sustituye los índices locales de MySQL. [Referencia de Vindexes](https://vitess.io/docs/24.0/reference/features/vindexes/).

Los nombres `-80` y `80-` representan rangos del espacio de identificadores en hexadecimal. No significan «clientes menores o mayores que 80». Tampoco garantizan que veinte clientes produzcan exactamente diez filas en cada lado.

Hay otra consecuencia: un identificador que debe ser único globalmente no queda protegido automáticamente por índices independientes en todos los shards. En este laboratorio, los IDs de pedidos se generan mediante una secuencia compartida. En un sistema real hay que revisar también las escrituras que proporcionan IDs explícitos y las restricciones que se quieren mantener.

## Un laboratorio con datos desde el principio

El repositorio contiene cuatro estados declarativos del clúster, los esquemas SQL, sus VSchema y `lab.py`, una herramienta en Python que ejecuta los pasos. Los binarios MySQL y `vtctldclient` se utilizan dentro del contenedor de la versión fijada.

Necesitas Docker arrancado, Minikube, kubectl, Python 3.10 o superior y recursos suficientes: cuatro CPU, unos 11 GB de RAM disponibles para Minikube y espacio en disco. **Las imágenes fijadas publican linux/amd64**. Si trabajas con Apple Silicon, ejecuta el laboratorio en una máquina o VM Linux amd64; no se presenta como compatible de forma nativa con ARM.

```bash
git clone https://github.com/pvtoCalvo/vitess-mysql-sharding-lab.git
cd vitess-mysql-sharding-lab
python3 lab.py up
python3 lab.py init
```

Se crea un perfil Minikube llamado `vitess-lab`, separado del contexto habitual de trabajo. La carga inicial contiene 20 clientes, 40 pedidos y dos productos ficticios. La herramienta comprueba que las filas esperadas están presentes.

Los manifiestos derivan del [ejemplo oficial de la release](https://github.com/vitessio/vitess/tree/v24.0.3/examples/operator), con ajustes de namespace, observación del operador y acceso a VTAdmin. Son una configuración de aprendizaje de un único nodo, con almacenamiento local para backups.

## Primera operación: separar clientes y pedidos

Creamos el keyspace de destino e iniciamos MoveTables:

```bash
python3 lab.py move-prepare
python3 lab.py move-create
python3 lab.py move-check
```

La operación equivalente de Vitess es:

```bash
vtctldclient --server localhost:15999 MoveTables \
  --target-keyspace customer --workflow commerce2customer \
  create --source-keyspace commerce --tables customer,corder
```

El comando muestra la sintaxis actual; desde el repositorio puedes ejecutarlo mediante `python3 lab.py vt MoveTables ...`, omitiendo el binario y el servidor, que aporta el wrapper.

MoveTables se apoya en VReplication para copiar y mantener los cambios mientras prepara el destino. El corte final puede introducir una breve ventana de bloqueo; la aplicación debe contemplar tiempos de espera y reintentos adecuados. «Online» no equivale a prometer una latencia idéntica durante todo el proceso. [Guía oficial de MoveTables](https://vitess.io/docs/24.0/user-guides/migration/move-tables/).

**VDiff** compara el origen y el destino. En el laboratorio se crea una ejecución nueva con un UUID concreto y se exige que termine, que no indique diferencias y que haya comparado filas. Validar tablas vacías ofrece muy poca información sobre la migración que nos interesa practicar.

```bash
python3 lab.py move-switch
python3 lab.py verify
```

Primero cambiamos las lecturas de las tablets `replica`; después, las escrituras de `primary`. Cada paso tiene su simulación previa. Mientras el workflow siga abierto y la replicación inversa permita hacerlo, podemos usar `move-reverse` para volver al origen.

Cuando el destino esté validado:

```bash
python3 lab.py move-complete --confirm-complete
```

Completar limpia el origen y cierra esa ventana de reversión. Debe ser una decisión separada de cambiar el tráfico.

## Segunda operación: pasar de un shard a dos

Antes de fragmentar, sustituimos AUTO_INCREMENT por secuencias de Vitess. Estas viven en `commerce`, que permanece sin fragmentar, mientras sus columnas asociadas están en `customer`.

La tabla de secuencia lleva el comentario exacto `vitess_sequence`; el VSchema la declara de tipo `sequence`. La herramienta calcula su punto inicial a partir del máximo ID existente. Los bloques en caché pueden dejar huecos: una secuencia no es una garantía de numeración consecutiva sin saltos.

**Durante `reshard-prepare` detenemos cualquier escritor adicional.** El cambio didáctico de AUTO_INCREMENT a secuencias no pretende automatizar una migración de esquema sin pausa para una aplicación real.

```bash
python3 lab.py reshard-prepare
python3 lab.py reshard-create
python3 lab.py reshard-check
python3 lab.py reshard-switch
```

Los shards de origen y destino coexisten durante la operación. Este consumo adicional de capacidad debe contemplarse antes de empezar, especialmente en entornos con volúmenes grandes.

La creación del workflow usa esta sintaxis:

```bash
vtctldclient --server localhost:15999 Reshard \
  --target-keyspace customer --workflow customer2shards \
  create --source-shards=- --target-shards=-80,80-
```

Después del cambio comprobamos tres cosas distintas:

```bash
python3 lab.py verify
python3 lab.py distribution
python3 lab.py sequence-check
```

La primera comprueba el conjunto de IDs iniciales; la segunda consulta ambos shards y suma sus filas; la tercera inserta un cliente y un pedido sin IDs explícitos. El VDiff previo aporta la comparación del contenido entre origen y destino. Ninguna comprobación aislada sustituye a las demás.

Si necesitamos volver atrás antes de completar, utilizamos `reshard-reverse`. Si todo está correcto:

```bash
python3 lab.py reshard-complete --confirm-complete
```

Además de completar el workflow, retiramos el shard antiguo del manifiesto deseado por el operador. Cambiar únicamente la topología sin reconciliar la configuración declarativa dejaría una intención de despliegue inconsistente.

## Lo que queda fuera del tutorial

El laboratorio permite estudiar enrutamiento y migraciones; no representa un despliegue listo para producción. Usa una cell, permisos MySQL amplios, acceso de laboratorio sin contraseña y una política de durabilidad simplificada.

Para un servicio real hay que concretar autenticación y TLS, restricciones de red, copias y restauraciones probadas, durabilidad, distribución entre dominios de fallo, observabilidad y procedimientos de actualización. También hay que medir las consultas que cruzan shards y decidir qué semántica de transacciones necesita la aplicación.

En esta entrega se han ejecutado las validaciones estáticas de los manifiestos y las pruebas de la lógica de la herramienta. **No se ha ejecutado el recorrido completo en Kubernetes en el equipo de preparación**, un Mac ARM con Docker detenido. El repositorio distingue esas comprobaciones de una prueba de integración y no atribuye resultados de rendimiento al ejemplo.

Vitess ayuda a gestionar una arquitectura de MySQL distribuido. La parte decisiva sigue estando en cómo distribuimos los datos, qué consultas hacemos y qué verificamos antes de mover el tráfico.

El [repositorio](https://github.com/pvtoCalvo/vitess-mysql-sharding-lab) incluye los pasos completos, las fuentes y los comandos de limpieza. Si probáis el recorrido con vuestra carga, contad qué clave de fragmentación elegisteis y qué consultas os obligaron a replantearla.
