# Vantarmor.Commands.

Bot de Discord basado en discord.py.

## Configuración en Railway

Variables necesarias:
- `DISCORD_TOKEN`: token privado del bot.
- `PREMIUM_MANAGER_IDS`: IDs de Discord autorizados para usar `/premium-generar-key`, separados por comas.
- `PREMIUM_USER_IDS`: opcional; usuarios con Premium permanente, separados por comas.

El bot se inicia con `python railway_start.py`. El lanzador aplica los parches de funciones y después ejecuta `app.py`. Los comandos slash se sincronizan en el servidor definido por `GUILD_ID` en `app.py`; confirma que el bot está instalado en ese servidor y que la aplicación tiene el scope `applications.commands`.

## Premium manual y keys

`premium_users.json` acepta IDs con Premium manual en este formato:

```json
{
  "123456789012345678": true
}
```

`/premium-generar-key` crea una key de un solo uso, válida por la duración elegida. El bot guarda solamente su hash en `premium_keys.json`. El backend web futuro deberá validar la key con `redeem_premium_key(key, discord_user_id)` después de autenticar la cuenta Discord.

Los archivos JSON deben estar en almacenamiento persistente de Railway, o se perderán al recrearse el contenedor. Los usuarios añadidos mediante `PREMIUM_USER_IDS` no necesitan escribirse en el JSON.

## Copias de seguridad

`/seguridad-copia` requiere una cuenta Premium y ser propietario o administrador. Se guardan categorías y canales de texto/voz, con permisos básicos. Restaurar recrea elementos faltantes y no borra los canales existentes. Las copias no contienen mensajes y el bot necesita el permiso `Administrar canales`.
