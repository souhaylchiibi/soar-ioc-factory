-- Création des bases au premier démarrage de PostgreSQL (volume vierge).
-- Le conteneur n8n n'a pas le droit de créer sa base : on l'anticipe ici.
SELECT 'CREATE DATABASE soar_ioc'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'soar_ioc') \gexec

SELECT 'CREATE DATABASE soar_n8n'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'soar_n8n') \gexec
