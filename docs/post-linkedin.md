En 2022 publiqué un artículo sobre cómo escalar MySQL horizontalmente con Vitess. Tocaba actualizarlo.

La nueva versión utiliza Vitess 24.0.3 y Operator 2.17.1, con un laboratorio en Kubernetes y código disponible en GitHub.

El recorrido incluye:

• Un conjunto inicial de clientes y pedidos.
• MoveTables para separar tablas entre keyspaces.
• Secuencias para sustituir AUTO_INCREMENT.
• Reshard para pasar de uno a dos shards.
• VDiff antes de cambiar el tráfico.
• Comprobación de distribución y pasos de reversión antes de completar el workflow.

Una idea que sigue siendo fundamental: añadir réplicas y fragmentar datos resuelven problemas distintos. La clave de fragmentación y las consultas de la aplicación determinan cuánto podemos aprovechar esa distribución.

También he separado lo que es un laboratorio de lo que necesita producción. Las imágenes fijadas son amd64 y el repo documenta sus requisitos y el alcance de las validaciones realizadas.

Artículo y código:
https://github.com/pvtoCalvo/vitess-mysql-sharding-lab

¿Qué os ha resultado más difícil al plantear sharding: elegir la clave, adaptar las consultas o preparar la operación?

#MySQL #Vitess #Kubernetes #Databases #Sharding #DevOps
