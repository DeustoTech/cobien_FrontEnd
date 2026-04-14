# Module de Visioconférence – Projet CoBien

Ce module couvre deux flux distincts :

1. Appel sortant depuis l'écran des contacts du meuble.
2. Appel entrant accepté depuis une notification système.

## Description générale

L'écran des contacts ne dépend pas du site web en temps réel pour s'afficher.
Les contacts visibles proviennent du fichier local `app/contacts/list_contacts.txt`
et des images déjà téléchargées dans `app/contacts/`.

Quand l'utilisateur appuie sur un contact valide :
- une fenêtre d'attente active s'affiche
- une requête HTTP est envoyée au backend/pizarra
- ensuite une fenêtre de succès ou d'erreur est affichée

Quand un appel entrant arrive :
- le backend publie une notification MQTT
- le frontend affiche la notification entrante
- si l'utilisateur accepte, `videocall_launcher.py` est lancé
- le launcher ouvre le portail web et informe le backend que l'appel a été accepté

## Flux actuel

### 1. Demande sortante depuis les contacts

1. `contactScreen.py` charge `list_contacts.txt`.
2. Seuls les contacts avec un `username` valide sont affichés.
3. Lors d'un appui sur un contact :
   - la fenêtre `Solicitando videollamada` apparaît
   - un `POST /pizarra/api/notify/` est envoyé
4. Si le backend répond correctement :
   - la fenêtre `Notificación enviada` s'affiche
5. En cas d'échec :
   - la fenêtre `Solicitud no enviada` s'affiche
   - les détails techniques restent cachés derrière `Mostrar detalles`

### 2. Appel entrant

1. Le backend publie une notification MQTT de type `videocall`.
2. `notification_manager.py` affiche la notification entrante.
3. Si l'utilisateur accepte :
   - un JSON temporaire est créé avec `room`, `device_id` et `identity`
   - `videocall_launcher.py` est lancé
   - le launcher ouvre `portal_videocall_url`
   - le launcher fait `POST /api/call-answered/`
4. À la fin de l'appel, la durée est enregistrée et le JSON temporaire est supprimé.

## Configuration pertinente

La configuration provient de `app/config/config.local.json`, section `services`.

Clés importantes :
- `notify_api_key`
- `pizarra_notify_url`
- `contacts_api_url`
- `portal_videocall_url`
- `portal_call_answered_url`
- `http_timeout_sec`

Et dans `settings` :
- `device_id`
- `videocall_room`

## Endpoints backend utilisés

- `POST /pizarra/api/notify/`
  Envoie une demande de visioconférence à l'utilisateur web.

- `GET /pizarra/api/contacts/?device_id=...`
  Retourne la liste de contacts synchronisable pour le meuble.

- `POST /pizarra/api/contacts/sync/`
  Publie via MQTT une demande de rafraîchissement des contacts.

- `POST /api/call-answered/`
  Informe le backend que le meuble a accepté l'appel.

## Codes d'erreur pour l'appel sortant

Quand une demande sortante échoue, la fenêtre montre d'abord un message simple.
Si l'utilisateur appuie sur `Mostrar detalles`, le code et le détail technique
deviennent visibles.

Codes actuels :
- `VC-CONFIG` : `notify_api_key` absent dans la configuration.
- `VC-DEVICE` : `device_id` absent dans la configuration.
- `VC-USER` : le contact n'a pas de destination valide.
- `VC-TIMEOUT` : le backend n'a pas répondu à temps.
- `VC-NET` : erreur de connexion avec le backend.
- `VC-REQ` : erreur HTTP générique côté client.
- `VC-401`, `VC-403`, `VC-404`, `VC-500`, etc. : réponse HTTP du backend.
- `VC-UNK` : erreur non classifiée.

## Validation des contacts

`list_contacts.txt` utilise le format :

```text
NomVisible=username_backend
```

Le frontend filtre maintenant les contacts invalides :
- les lignes sans `=` ne sont pas affichées
- les contacts avec un `username` vide ne sont pas affichés
- les contacts avec des caractères hors `[A-Za-z0-9_.-]` ne sont pas affichés

Exemples valides :

```text
Jules=jules_pourret
Capucine=capucine
Jojo=joisback
```

Exemples invalides :

```text
Mathurin=
Marie=
Simona=
```

## Notes opérationnelles

- Si le site web est indisponible, les contacts peuvent rester visibles car ils
  proviennent du cache local.
- Voir des contacts n'implique pas que la synchronisation ou l'appel fonctionneront.
- `videocall_launcher.py` peut être lancé isolément pour des tests, mais le flux
  normal utilise le JSON temporaire généré par `notification_manager.py`.
