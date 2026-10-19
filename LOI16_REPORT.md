# Étude du fonds de prévoyance et carnet d’entretien Metra

Dans Telegram : **Metra Consultation → Loi 16 → Write a report → projet**.
Ajouter et classer les photographies, puis choisir **📊 Données Loi 16**.

1. **Hypothèses financières** : année monétaire, horizon (minimum 25 ans), date
   et solde initial exacts, cotisation annuelle, inflation, rendement net,
   indexation des cotisations et base des coûts.
2. Choisir chaque composante A001, A002, etc. Compléter quantité, installation,
   durée de vie, vie résiduelle, intervention majeure, année, coût total de
   référence, source, cycle et usage restreint, puis entretien courant.
3. Revenir aux photos et sélectionner **Finish inspection**. La livraison
   existante fournit le Word et le PDF. Les autres services gardent leur moteur.

Les montants sont saisis sans symbole monétaire ni intervalle; les taux dans
Telegram sont des pourcentages (2,5 signifie 2,5 %). Dans les structures Python,
les taux sont des fractions (0.025). Le coût saisi est un montant total, avec les
taxes, honoraires et contingences déclarés dans la base des coûts; le moteur
n’ajoute aucune taxe implicite. Chaque groupe photo représente une fiche
d’inventaire : éviter les doublons de composantes financières en regroupant les
photos du même élément.

Les hypothèses financières sont conservées par projet. Les fiches techniques
restent dans la session avec les groupes de photos; une nouvelle inspection
demande une nouvelle validation des fiches. Une donnée inconnue bloque le
calcul, mais permet un rapport d’inventaire à compléter. Une composante dont
l’intervention est hors horizon peut avoir une année postérieure à l’horizon;
elle reste inventoriée sans dépense dans la période.

Le PDF est construit à partir des mêmes contenus que le Word et livré comme
PDF associé; le convertisseur historique qui omet les tableaux est évité pour
ce rapport. La pagination Word et PDF peut différer. Le graphique Word utilise
CairoSVG; le graphique PDF est vectoriel.

## Méthode de calcul

- Horizon inclusif : année de référence à année de référence + horizon - 1.
- Inflation des coûts depuis l’année de référence; récurrence selon le cycle.
- Cotisations en début d’année, paiement des travaux, puis intérêts de fin
  d’année sur le solde positif. Pas d’intérêts fictifs sur une dette.
- Scénarios : cotisation actuelle et cotisation initiale minimale calculée
  par recherche au cent près, avec la même indexation annuelle.
- Réserves nécessaires calculées à rebours pour les cotisations du scénario,
  avec objectif final nul. Aucune marge de sécurité implicite.
- Ventilation proposée pour usage restreint proportionnelle au total des
  dépenses futures identifiées; à valider selon la déclaration de copropriété.
- Aucune cotisation spéciale dans ces deux scénarios. L’entretien courant est
  présenté séparément et n’est pas débité du fonds de prévoyance.

Ces conventions annuelles doivent être validées selon les dates réelles de
paiement, la déclaration de copropriété et les exigences professionnelles.
Le seuil calculé n’est pas une recommandation professionnelle automatique.

Référence réglementaire : CCQ, r. 8.01, articles 1 à 9, texte officiel consulté
le 19 octobre 2026, version affichée au 1er juillet 2026 :
https://www.legisquebec.gouv.qc.ca/fr/document/rc/CCQ,%20r.%208.01

Les annexes comprennent les observations et photographies, l’échéancier des
travaux majeurs, l’entretien courant, le calendrier annuel à compléter et le
registre des travaux et pièces justificatives. La déclaration d’examen sur
place et de prise de connaissance des documents ainsi que la signature et la
recommandation de l’auteur restent à compléter après révision professionnelle.

Validation : `python -m unittest discover -s tests -v`.
