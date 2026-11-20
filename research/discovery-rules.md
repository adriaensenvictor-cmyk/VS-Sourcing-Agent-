# Ce que FirstTrace vérifie pour trouver une startup

Le mode **Live discovery** applique des règles Python à des sources publiques. Il collecte d’abord des pistes, estime lesquelles conviennent à la présélection, puis les classe. Le workflow n8n lance ce même moteur. Le résumé IA du dossier est une action facultative de lecture des preuves.

## 1. Collecter les pistes

| Source | Règles du scan |
| --- | --- |
| **TUM Venture Labs** | Lit jusqu’à 100 fiches d’équipe, par mise à jour la plus récente du sitemap. Cherche soit un indice de stade précoce, comme un MVP ou une preuve de concept, soit un indice de validation produit, comme un prototype testé ou des pilotes. Demande aussi un indice d’origine universitaire, d’équipe fondatrice ou de validation produit. Une fiche peut aussi passer sans prototype si elle nomme les fondateurs et documente l’origine universitaire, le rôle de l’équipe fondatrice ou l’intention de créer l’entreprise. Écarte les fiches dont le texte annonce une levée selon les motifs du collecteur. |
| **TU Berlin** | Ouvre jusqu’à 12 fiches, en privilégiant la cohorte de l’année courante puis celles des deux années précédentes. Extrait le nom du projet, la description, le bloc équipe et la mention éventuelle d’un financement public EXIST. Le pipeline écarte la fiche générique EXIST Women. |
| **UnternehmerTUM Incubator** | Lit jusqu’à 35 cartes qui contiennent un nom et une description. Conserve la page officielle du portfolio et le lien du projet si disponible. L’adresse de l’incubateur ne suffit pas pour renseigner le pays du projet. |
| **imec.istart** | Lit jusqu’à 25 fiches portant l’année courante ou l’une des deux années précédentes. Extrait nom, description, pays indiqué et lien de la fiche. L’année est celle du portfolio. |
| **BayStartUP** | Lit jusqu’à 30 nominations de la phase 1 du concours 2026 de Munich, dans les catégories numérique/logiciel, sciences de la vie et industrie/énergie. Extrait nom, lieu et description. La date de publication du palmarès sert de trace publique lorsqu’elle est lisible. |
| **Show HN** | Cherche les publications Show HN des 365 derniers jours par défaut, jusqu’à 100 résultats par requête via Algolia. Requêtes de lieu : Berlin, Munich, München, Hamburg, Cologne, Frankfurt et Germany. Le texte du post doit indiquer un lien de localisation exploitable, par exemple une équipe qui dit travailler sur place. Écarte notamment les projets de week-end, devoirs et projets « for fun ». Note les mentions de clients, pilotes, tarifs, accès anticipé, équipe ou prototype. |
| **GitHub** | Prend d’abord les dépôts publics déjà reliés à une piste. Pour remplir le quota restant, cherche les paires exactes `"Germany" "early access"` et `"Europe" "design partners"` dans les README de dépôts non forkés et non archivés, créés depuis moins de 300 jours et mis à jour depuis moins de 75 jours. Le tableau de bord et n8n analysent jusqu’à quatre dépôts, 50 commits récents et 20 sorties par dépôt. Une collaboration suivie demande au moins deux contributeurs non bots, actifs chacun sur au moins deux semaines. Un fondateur ou un pays est extrait quand le README l’indique explicitement. |

Fraunhofer AHEAD, SpinLab et RootCamp ajoutent des équipes tirées d’annonces officielles datées. HPI Engine fournit des fiches d’écosystème, y compris des alumni. La vue **Incubators in Germany** indexe les centres publics du BVIZ et donne accès aux répertoires nationaux. Les centres avec un roster exploitable alimentent le scan via un connecteur dédié.

Code : [orchestration](../discovery_pipeline.py), [TUM](../campus.py), [TU Berlin](../engine.py), [portefeuilles](../programmes.py), [Show HN](../sourcing.py), [GitHub](../emergence.py).

Le moteur rapproche les pistes par URL normalisée du projet ou par dépôt GitHub précis. La seule similitude de noms ne déclenche pas de fusion. Le mode **Verified research snapshot** utilise des dossiers préparés. Le pipeline live inclut également une référence TUM contrôlée et étiquetée séparément concernant un projet de camions autonomes. Le dossier d’une startup détectée en direct peut recevoir des détails vérifiés manuellement.

## 2. Chercher les signaux et décider qui présélectionner

Le moteur lit les descriptions, les posts et les README. Il conserve le texte extrait et sa source. Une correspondance de texte est une **hypothèse** tant que le fait reste à confirmer.

| Signal | Exemples des formulations recherchées |
| --- | --- |
| Immatriculation | `incorporated`, `registered our company`, `registered the company` |
| Lancement | `we launched`, `now available`, `public beta`, `went live` |
| Liste d’attente | `join our waitlist`, `join the waiting list`, `sign up for early access` |
| Clients ou pilote | `pilot customer`, `paying customers`, `signed a pilot` |
| Recrutement | `we are hiring`, `we're hiring`, `open positions` |
| Incubateur | `accepted into` ou `joined`, suivi à proximité de `accelerator` ou `incubator` |
| Commercialisation | `go-to-market`, `commercial launch`, `licensing agreement`, `paid plans` |
| Prototype | `working prototype`, `research-validated prototype`, `pre-alpha`, `proof of concept` |

Le **parcours des fondateurs** est recherché automatiquement dans les biographies lues chez TUM Venture Labs, et peut être complété par des sources contrôlées. Le détecteur exige une phrase attribuable à une personne nommée et une mention explicite d’emploi passé ou de création antérieure, par exemple `worked at`, `ex-`, `previously founded` ou `founded and sold`. Le [répertoire des employeurs](../founder_employers.py) couvre les réseaux d’anciens salariés en Allemagne et en Europe, les grandes entreprises tech, la finance et l’industrie. La présence du nom d’un employeur ne donne aucun point à elle seule. La recherche part des projets repérés dans les sources connectées. [Détection du parcours](../founder_signals.py)

Une piste peut entrer dans la **présélection** si le moteur lui attribue un pays de sa liste européenne, qu’il ne détecte ni levée confirmée/stade seed ni alerte de type projet sans intention de créer une entreprise, et qu’au moins un des chemins suivants est documenté :

- Un indice d’immatriculation, lancement, liste d’attente, pilote, recrutement, accélérateur ou commercialisation.
- Une équipe en amont du produit, documentée par une sélection publique de programme publiée dans les 365 derniers jours, une équipe universitaire avec preuve d’accompagnement, ou une intention de créer l’entreprise attribuable à des fondateurs publiquement nommés.

La présélection publie jusqu’à dix dossiers. **Early follow-up only** regroupe les dossiers de la deuxième voie sans signal de commercialisation, y compris au-delà de la présélection. Pour les programmes sans pays d’implantation documenté, choisir **All locations**. Le filtre d’âge **2 ou 3 ans** est distinct et s’appuie sur les dates sourcées.

Un financement public est conservé séparément de l’equity. Le statut « aucune levée publique trouvée » correspond à une recherche documentée et limitée. « Inconnu » indique que le dossier reste à vérifier. La recherche Brave facultative existe dans le CLI avec `--search-funding` et une clé dédiée. Elle est désactivée dans les scans ordinaires du tableau de bord et de n8n. [Règles de qualification](../qualification.py) · [Présélection](../emergence.py)

## 3. Classer les dossiers

Chaque critère rapporte ses points une seule fois. La note s’appuie sur des preuves revues et sourcées. Un critère côté équipe doit pouvoir être attribué à une personne nommée. La note reste **provisoire** tant que des critères manquent, et **en attente** s’il manque un axe entier ou que les preuves se contredisent.

| Équipe | Sur 60 | Projet | Sur 40 |
| --- | ---: | --- | ---: |
| Expertise du domaine | 12 | Importance du problème | 6 |
| Réalisations pertinentes | 9 | Différenciation | 6 |
| Technologie déjà construite | 12 | Opportunité de marché | 6 |
| Expérience opérationnelle | 12 | Faisabilité technique | 8 |
| Équipe complémentaire | 6 | Voie de commercialisation | 6 |
| Contribution à la recherche | 9 | Validation client | 8 |

Les dossiers allemands passent en premier. Dans chaque groupe, les notes calculées sont triées par ordre décroissant, devant les notes en attente. L’**ancien score de signaux précoces** départage les égalités et trie les dossiers en attente. Il répartit ses plafonds entre exécution technique (20), équipe (15), commercialisation (30), précocité (10), potentiel marché (15) et qualité des preuves (10). [Calcul de la note](../founder_fit.py) · [Score de signaux précoces](../emergence.py)
