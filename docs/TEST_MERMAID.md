# Test Mermaid Preview

Ouvrez ce fichier dans VS Code et appuyez sur **Ctrl+Shift+V** (ou **Cmd+Shift+V** sur Mac) pour voir la prévisualisation.

## Test 1 : Graphe Simple

```mermaid
graph LR
    A[Début] --> B[Milieu]
    B --> C[Fin]

    style A fill:#ccffcc
    style C fill:#ffcccc
```

## Test 2 : Diagramme de Séquence

```mermaid
sequenceDiagram
    participant User
    participant System
    participant API

    User->>System: Demande
    System->>API: Requête
    API-->>System: Réponse
    System-->>User: Résultat
```

## Test 3 : Diagramme d'États

```mermaid
stateDiagram-v2
    [*] --> Inactif
    Inactif --> Actif: Démarrer
    Actif --> EnCours: Traiter
    EnCours --> Terminé: Finir
    Terminé --> [*]
```

## Test 4 : Graphe Complexe (Architecture)

```mermaid
graph TB
    subgraph "Frontend"
        UI[Interface Utilisateur]
    end

    subgraph "Backend"
        API[API]
        Logic[Logique Métier]
        DB[(Base de Données)]
    end

    UI --> API
    API --> Logic
    Logic --> DB

    style UI fill:#e3f2fd
    style API fill:#fff3e0
    style Logic fill:#e8f5e9
    style DB fill:#f3e5f5
```

## Comment utiliser

1. **Ouvrir la prévisualisation** : `Ctrl+Shift+V` (Windows/Linux) ou `Cmd+Shift+V` (Mac)
2. **Prévisualisation côte à côte** : `Ctrl+K V` puis ouvrir le fichier

Si vous voyez les diagrammes rendus (pas le code), ça fonctionne ! ✅

Si vous voyez juste le code Mermaid, l'extension n'est pas active. Redémarrez VS Code.
