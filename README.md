# Vantarmor.Commands.

Bot de Discord basado en discord.py.

## Premium manual

Los usuarios Premium se guardan en `premium_users.json` como IDs de Discord y `true`, por ejemplo:

```json
{
  "123456789012345678": true
}
```

También se pueden establecer IDs permanentes en la variable de Railway `PREMIUM_USER_IDS`, separados por comas. Para usuarios añadidos al archivo JSON, conserva ese archivo en un volumen persistente de Railway o usa la variable de entorno; el almacenamiento efímero puede perderse al redeplegar.

Para generar keys desde Discord, configura `PREMIUM_MANAGER_IDS` en Railway con los IDs de las cuentas autorizadas, separados por comas. Esas cuentas podrán usar `/premium-generar-key` e indicar la duración entre 1 y 3650 días. La key se muestra una sola vez en una respuesta privada y su hash se guarda en `premium_keys.json`.

El backend web que se implemente después deberá validar una key llamando a `redeem_premium_key(key, discord_user_id)` desde `premium_backup_system.py`. La key es de un solo uso. Para producción, guarda `premium_users.json` y `premium_keys.json` en almacenamiento persistente o migra a una base de datos compartida antes de desplegar el sitio.

## Copias de seguridad

`/seguridad-copia` y la restauración requieren que el usuario tenga Premium y sea propietario o administrador del servidor. Se respalda la estructura de categorías y canales de texto/voz, así como permisos básicos. La restauración recrea elementos faltantes y **no borra canales existentes**. No guarda mensajes ni garantiza la recuperación de todo tipo de canal.
