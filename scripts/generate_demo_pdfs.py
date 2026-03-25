#!/usr/bin/env python3
"""Generate 27 realistic German politics organization PDFs for RAG demo."""

import os
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY

OUTPUT_DIR = "/root/marcello2304/demo_docs"
os.makedirs(OUTPUT_DIR, exist_ok=True)

styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name='TitleDE', fontSize=18, leading=22, alignment=TA_CENTER, spaceAfter=20, fontName='Helvetica-Bold'))
styles.add(ParagraphStyle(name='H1', fontSize=14, leading=18, spaceBefore=16, spaceAfter=8, fontName='Helvetica-Bold'))
styles.add(ParagraphStyle(name='H2', fontSize=12, leading=15, spaceBefore=12, spaceAfter=6, fontName='Helvetica-Bold'))
styles.add(ParagraphStyle(name='BodyDE', fontSize=10, leading=14, alignment=TA_JUSTIFY, spaceAfter=6, fontName='Helvetica'))
styles.add(ParagraphStyle(name='BulletDE', fontSize=10, leading=14, leftIndent=20, bulletIndent=10, spaceAfter=4, fontName='Helvetica'))


def build_pdf(filename, title, content_func):
    path = os.path.join(OUTPUT_DIR, filename)
    doc = SimpleDocTemplate(path, pagesize=A4,
                            leftMargin=2*cm, rightMargin=2*cm,
                            topMargin=2.5*cm, bottomMargin=2.5*cm)
    story = []
    story.append(Paragraph(title, styles['TitleDE']))
    story.append(Spacer(1, 12))
    content_func(story)
    doc.build(story)
    print(f"  Created: {filename}")


def add_para(story, text, style='BodyDE'):
    story.append(Paragraph(text, styles[style]))

def add_h1(story, text):
    story.append(Paragraph(text, styles['H1']))

def add_h2(story, text):
    story.append(Paragraph(text, styles['H2']))

def add_bullet(story, text):
    story.append(Paragraph(f"\u2022 {text}", styles['BulletDE']))

def add_spacer(story, h=8):
    story.append(Spacer(1, h))

def add_page_break(story):
    story.append(PageBreak())


# ==============================================================================
# KATEGORIE 1: Politik-Strategie
# ==============================================================================

def wahlkampf_strategie_2026(story):
    add_para(story, "Herausgegeben vom Bundesvorstand | Stand: Januar 2026 | Vertraulich")
    add_para(story, "Die vorliegende Strategie beschreibt den digitalen Wahlkampfansatz unserer Partei "
             "fuer die Bundestagswahl 2026. Sie umfasst die Analyse der Zielgruppen, die Auswahl der "
             "Kommunikationskanaele, die Budgetverteilung sowie den zeitlichen Rahmen aller Massnahmen.")

    add_h1(story, "1. Zielgruppen-Analyse")
    add_para(story, "Unsere primaere Zielgruppe sind Waehlerinnen und Waehler im Alter von 25 bis 45 Jahren, "
             "die ueber digitale Kanaele erreichbar sind. Sekundaere Zielgruppen umfassen Erstwahler (18-24 Jahre) "
             "sowie die Generation 55+, die zunehmend soziale Medien nutzt. Laut unserer internen Erhebung vom "
             "November 2025 nutzen 78% der Zielgruppe Instagram, 65% YouTube und 42% TikTok regelmaessig.")
    add_para(story, "Die regionale Schwerpunktsetzung liegt auf den Bundeslaendern Nordrhein-Westfalen, Bayern "
             "und Baden-Wuerttemberg, wo insgesamt 47 Direktmandate verteidigt werden muessen. In Ostdeutschland "
             "wird eine gezielte Rueckgewinnungsstrategie umgesetzt.")

    add_h1(story, "2. Social-Media-Kanaele")
    add_bullet(story, "Instagram: 3 Posts pro Tag, Stories taeglich, Reels 5x pro Woche. Budget: 180.000 Euro")
    add_bullet(story, "TikTok: 2 Kurzvideos taeglich, Trend-Adaptionen. Budget: 120.000 Euro")
    add_bullet(story, "YouTube: Wochentliches Erklaervideo, Livestreams bei Events. Budget: 95.000 Euro")
    add_bullet(story, "Facebook: Community-Management, Veranstaltungshinweise. Budget: 60.000 Euro")
    add_bullet(story, "X (Twitter): Echtzeit-Kommunikation, Pressereaktionen. Budget: 45.000 Euro")

    add_page_break(story)
    add_h1(story, "3. Budget-Verteilung Gesamtueberblick")
    add_para(story, "Das Gesamtbudget fuer den digitalen Wahlkampf betraegt 1.850.000 Euro. Die Verteilung "
             "erfolgt wie folgt: Social-Media-Werbung 500.000 Euro (27%), Content-Produktion 350.000 Euro (19%), "
             "Personalkosten digitales Team 420.000 Euro (23%), Technische Infrastruktur 180.000 Euro (10%), "
             "Datenanalyse und Monitoring 200.000 Euro (11%), Reserve 200.000 Euro (10%).")
    add_para(story, "Die monatliche Freigabe erfolgt durch den Schatzmeister in Abstimmung mit der Wahlkampfleitung. "
             "Ab Mai 2026 wird das Budget um 40% erhoeht fuer die heisse Wahlkampfphase.")

    add_h1(story, "4. Timeline")
    add_bullet(story, "Januar - Maerz 2026: Aufbauphase, Team-Rekrutierung, Content-Planung")
    add_bullet(story, "April - Juni 2026: Intensivierung der Social-Media-Praesenz")
    add_bullet(story, "Juli - August 2026: Sommerkampagne mit regionalem Fokus")
    add_bullet(story, "September 2026: Schlussphase, taegliche Livestreams, Mobilisierung")
    add_bullet(story, "Wahltag: 28. September 2026 (Annahme)")

    add_page_break(story)
    add_h1(story, "5. Erfolgsmessung und KPIs")
    add_para(story, "Die Erfolgsmessung erfolgt anhand folgender KPIs: Reichweite pro Woche (Ziel: 5 Mio.), "
             "Engagement-Rate (Ziel: 4,5%), Follower-Wachstum (Ziel: +150.000 bis September), "
             "Conversion zu Newsletter-Abonnenten (Ziel: 80.000 neue), Share of Voice gegenueber "
             "Mitbewerbern (Ziel: mindestens 22%). Das Monitoring-Team unter Leitung von Frau Dr. Petra Klein "
             "erstellt woechentliche Reports fuer den Vorstand.")


def positionspapier_klimapolitik(story):
    add_para(story, "Beschluss des Parteivorstands vom 15. Februar 2026 | Dokumentennummer: PP-2026-003")

    add_h1(story, "Praeambel")
    add_para(story, "Die Klimakrise ist die groesste Herausforderung unserer Zeit. Als verantwortungsvolle "
             "politische Kraft legen wir mit diesem Positionspapier fuenf Kernforderungen vor, die ambitionierten "
             "Klimaschutz mit sozialer Gerechtigkeit und wirtschaftlicher Wettbewerbsfaehigkeit verbinden. "
             "Das Papier wurde unter Einbeziehung von 14 Fachexperten und 3 Buergerraeten erarbeitet.")

    add_h1(story, "Kernforderung 1: Klimaneutralitaet bis 2040")
    add_para(story, "Deutschland muss bis 2040 klimaneutral werden. Dies erfordert eine Reduktion der "
             "Treibhausgasemissionen um 80% bis 2035 gegenueber 1990. Der Kohleausstieg muss bis 2030 "
             "abgeschlossen sein. Wir fordern ein verbindliches Klimaschutzgesetz mit jaehrlichen "
             "Sektorzielen und automatischen Nachsteuerungsmechanismen. Geschaetzte Investitionen: 45 Mrd. Euro.")

    add_h1(story, "Kernforderung 2: Erneuerbare Energien als Wirtschaftsmotor")
    add_para(story, "Der Ausbau erneuerbarer Energien muss auf 95% Anteil am Strommix bis 2035 gesteigert "
             "werden. Dazu fordern wir: Verdreifachung der Photovoltaik-Kapazitaet, 2% der Landesflaeche "
             "fuer Windenergie, Aufbau von 50 GW Speicherkapazitaet. Die Genehmigungsverfahren muessen "
             "auf maximal 6 Monate verkuerzt werden. Geschaetzte Investitionen: 120 Mrd. Euro bis 2035.")

    add_page_break(story)
    add_h1(story, "Kernforderung 3: Klimasozialfonds")
    add_para(story, "Ein Klimasozialfonds mit jaehrlich 8 Mrd. Euro soll einkommensschwache Haushalte bei "
             "der Transformation unterstuetzen. Dies umfasst: Klimageld von 200 Euro pro Person und Jahr, "
             "Foerderprogramm fuer energetische Gebaeudesanierung (bis zu 80% Kostenuebernahme fuer "
             "Geringverdiener), kostenloser OEPNV fuer Empfaenger von Buergergeld.")

    add_h1(story, "Kernforderung 4: Gruene Industriepolitik")
    add_para(story, "Wir fordern ein Sonderprogramm von 30 Mrd. Euro fuer die Transformation der "
             "energieintensiven Industrie. Schwerpunkte sind gruener Stahl, Chemie und Zement. "
             "Carbon-Contracts-for-Difference sollen Planungssicherheit geben. Deutsche Unternehmen "
             "sollen zu Weltmarktfuehrern in Klimatechnologien werden.")

    add_h1(story, "Kernforderung 5: Internationale Klimafinanzierung")
    add_para(story, "Deutschlands Beitrag zur internationalen Klimafinanzierung muss auf 12 Mrd. Euro "
             "jaehrlich steigen. Wir unterstuetzen den Loss-and-Damage-Fonds und fordern eine "
             "Klimapartnerschaft mit mindestens 20 Laendern des Globalen Suedens.")

    add_h1(story, "Finanzierungskonzept")
    add_para(story, "Die Gesamtfinanzierung belaeuft sich auf ca. 250 Mrd. Euro bis 2040. "
             "Finanzierungsquellen: CO2-Bepreisung (Erhoehung auf 180 Euro/Tonne bis 2030) bringt "
             "ca. 80 Mrd. Euro, Abbau klimaschaedlicher Subventionen 65 Mrd. Euro, gruene Bundesanleihen "
             "60 Mrd. Euro, EU-Foerdermittel 25 Mrd. Euro, Restfinanzierung ueber Haushalt 20 Mrd. Euro.")


def positionspapier_sozialpolitik(story):
    add_para(story, "Beschluss des erweiterten Vorstands vom 3. Maerz 2026 | Dokumentennummer: PP-2026-005")

    add_h1(story, "I. Rentenpolitik: Sicherheit im Alter")
    add_para(story, "Das gesetzliche Rentenniveau muss dauerhaft bei mindestens 50% stabilisiert werden. "
             "Wir fordern die Einfuehrung einer Buergerversicherung, in die alle Erwerbstaetigen einzahlen, "
             "einschliesslich Beamte, Selbststaendige und Abgeordnete. Die Mindesthrente soll auf 1.350 Euro "
             "netto angehoben werden. Kindererziehungszeiten und Pflegezeiten muessen staerker angerechnet werden. "
             "Der Renteneintritt bleibt flexibel: ab 63 Jahren mit Abschlaegen, ab 67 Jahren ohne Abschlaege. "
             "Fuer koerperlich Taetige soll eine Regelung ab 62 Jahren geschaffen werden.")

    add_h1(story, "II. Gesundheitspolitik: Versorgung fuer alle")
    add_para(story, "Die Zwei-Klassen-Medizin muss beendet werden. Wir fordern eine solidarische "
             "Gesundheitsversicherung mit einheitlichem Leistungskatalog. Die Wartezeiten auf Facharzttermine "
             "duerfen maximal 4 Wochen betragen. Die Krankenhausreform muss qualitaetsorientiert umgesetzt werden "
             "mit Sicherstellung der Versorgung in laendlichen Raeumen. Investitionen in die Digitalisierung "
             "des Gesundheitswesens: 15 Mrd. Euro bis 2030. Pflegekraefte sollen mindestens 4.200 Euro "
             "brutto im Monat verdienen, Ausbildungsverguetung ab dem ersten Tag.")

    add_page_break(story)
    add_h1(story, "III. Wohnungspolitik: Bezahlbares Wohnen")
    add_para(story, "Jedes Jahr muessen mindestens 400.000 neue Wohnungen gebaut werden, davon 150.000 "
             "Sozialwohnungen. Die Mietpreisbremse wird verschaerft: maximale Erhoehung von 5% in 3 Jahren "
             "in angespannten Maerkten. Spekulation mit Wohnraum wird durch eine Bodenwertzuwachssteuer "
             "eingedaemmt. Kommunen erhalten ein Vorkaufsrecht bei Immobilienverkaeufen. Das Wohngeld "
             "wird um durchschnittlich 30% erhoeht und automatisch an die Mietentwicklung angepasst.")

    add_h1(story, "IV. Finanzierung der Sozialpolitik")
    add_para(story, "Die Finanzierung erfolgt durch: Wiederanhebung des Spitzensteuersatzes auf 49% ab "
             "einem Einkommen von 250.000 Euro jaehrlich, Einfuehrung einer Vermoegenssteuer von 1% ab "
             "2 Mio. Euro Nettovermoegen, Finanztransaktionssteuer von 0,1%, Schliessung von Steuerschlupfloechern "
             "mit geschaetztem Mehraufkommen von 15 Mrd. Euro jaehrlich.")

    add_h1(story, "V. Massnahmenzeitplan")
    add_bullet(story, "2026: Gesetzentwurf Buergerversicherung, Anpassung Wohngeld")
    add_bullet(story, "2027: Einfuehrung Mindesthrente, Pflegeloehne erhoehen")
    add_bullet(story, "2028: Umsetzung Krankenhausreform, 100.000 Sozialwohnungen")
    add_bullet(story, "2029: Evaluation und Nachsteuerung aller Massnahmen")


def interne_satzung(story):
    add_para(story, "Fassung vom 22. November 2025 | Beschlossen auf dem 47. Ordentlichen Parteitag")

    add_h1(story, "Paragraf 1: Name, Sitz und Taetigkeitsgebiet")
    add_para(story, "Der Verein fuehrt den Namen 'Demokratische Zukunftspartei e.V.' (DZP). Er hat seinen "
             "Sitz in Berlin. Das Taetigkeitsgebiet erstreckt sich auf das gesamte Gebiet der Bundesrepublik "
             "Deutschland. Der Verein ist im Vereinsregister des Amtsgerichts Berlin-Charlottenburg eingetragen. "
             "Die Rechtsgrundlage bilden das BGB (Paragraf 21 ff.), das Parteiengesetz (PartG) sowie diese Satzung.")

    add_h1(story, "Paragraf 2: Zweck und Aufgaben")
    add_para(story, "Zweck des Vereins ist die Mitwirkung an der politischen Willensbildung gemaess Artikel "
             "21 des Grundgesetzes. Der Verein verfolgt ausschliesslich und unmittelbar gemeinnuetzige Zwecke "
             "im Sinne des Abschnitts 'Steuerbeguenstigte Zwecke' der Abgabenordnung. Die Aufgaben umfassen: "
             "politische Bildung, Aufstellung von Kandidaten fuer Wahlen, Erarbeitung politischer Programme, "
             "Oeffentlichkeitsarbeit und Mitgliederpflege.")

    add_page_break(story)
    add_h1(story, "Paragraf 3: Mitgliedschaft")
    add_para(story, "Mitglied kann jede natuerliche Person werden, die das 16. Lebensjahr vollendet hat und "
             "die Grundsaetze des Vereins anerkennt. Der Aufnahmeantrag ist schriftlich an den Vorstand zu "
             "richten. Ueber die Aufnahme entscheidet der Vorstand innerhalb von 4 Wochen. Die Mitgliedschaft "
             "endet durch Austritt (schriftlich, 3 Monate Kuendigungsfrist), Ausschluss (bei schwerwiegenden "
             "Verfehlungen, Beschluss mit 2/3-Mehrheit des Vorstands) oder Tod.")

    add_h1(story, "Paragraf 4: Organe des Vereins")
    add_para(story, "Die Organe des Vereins sind: a) die Mitgliederversammlung als hoechstes Beschlussorgan, "
             "b) der Vorstand, c) der Parteirat als beratendes Gremium, d) das Schiedsgericht zur Schlichtung "
             "interner Streitigkeiten. Die Mitgliederversammlung tritt mindestens einmal jaehrlich zusammen "
             "und wird mit einer Frist von 6 Wochen einberufen.")

    add_h1(story, "Paragraf 5: Vorstand")
    add_para(story, "Der Vorstand besteht aus mindestens 5 und hoechstens 9 Mitgliedern. Er wird fuer 2 Jahre "
             "gewaehlt. Wiederwahl ist zulaessig. Der Vorstand fuehrt die laufenden Geschaefte und vertritt "
             "den Verein nach aussen. Beschluesse werden mit einfacher Mehrheit gefasst, bei Stimmengleichheit "
             "entscheidet die Stimme des Vorsitzenden.")

    add_h1(story, "Paragraf 6: Finanzen")
    add_para(story, "Der Verein finanziert sich durch Mitgliedsbeitraege, Spenden, oeffentliche Zuwendungen "
             "und sonstige Einnahmen. Der Jahresbeitrag wird von der Mitgliederversammlung festgesetzt. "
             "Der Schatzmeister legt jaehrlich einen Rechenschaftsbericht vor. Die Buecher werden von "
             "zwei gewaehlten Kassenprufern geprueft. Ueber die Verwendung der Mittel entscheidet der Vorstand "
             "im Rahmen des von der Mitgliederversammlung beschlossenen Haushaltsplans.")

    add_page_break(story)
    add_h1(story, "Paragraf 7: Satzungsaenderung und Aufloesung")
    add_para(story, "Satzungsaenderungen benoetigen eine 2/3-Mehrheit der anwesenden stimmberechtigten "
             "Mitglieder auf einer ordentlichen Mitgliederversammlung. Aenderungsantraege muessen 4 Wochen "
             "vor der Versammlung schriftlich eingereicht werden. Die Aufloesung des Vereins kann nur mit "
             "3/4-Mehrheit beschlossen werden. Bei Aufloesung faellt das Vermoegen an eine gemeinnuetzige "
             "Organisation, die von der letzten Mitgliederversammlung bestimmt wird.")


def gremienstruktur(story):
    add_para(story, "Stand: Maerz 2026 | Letzte Aktualisierung nach der Vorstandswahl vom 22.11.2025")

    add_h1(story, "1. Geschaeftsfuehrender Vorstand")
    add_para(story, "Vorsitzende: Dr. Maria Schneider, Stellvertreter: Thomas Weber, Schatzmeister: Lisa Hartmann")
    add_para(story, "Dr. Maria Schneider (52) leitet den Vorstand seit November 2025. Sie ist promovierte "
             "Politikwissenschaftlerin und war zuvor 8 Jahre Landesvorsitzende in Nordrhein-Westfalen. "
             "Thomas Weber (47) ist Rechtsanwalt und seit 2020 im Bundesvorstand taetig. Lisa Hartmann (39) "
             "ist Wirtschaftsprueferin und verantwortet seit 2023 die Finanzen der Partei.")

    add_h1(story, "2. Erweiterter Vorstand")
    add_bullet(story, "Politische Geschaeftsfuehrerin: Dr. Claudia Reinhardt")
    add_bullet(story, "Pressesprecher: Markus Brenner")
    add_bullet(story, "Beisitzer: Stefan Maier, Ayse Yilmaz, Friedrich Baumann")
    add_bullet(story, "Jugendvertreterin: Lena Fischer")
    add_para(story, "Der erweiterte Vorstand tagt alle 14 Tage, in der Regel montags um 18:00 Uhr. "
             "Beschluesse werden mit einfacher Mehrheit gefasst. Die Sitzungen werden von der "
             "Geschaeftsstelle protokolliert. Protokolle sind innerhalb von 5 Werktagen zu versenden.")

    add_page_break(story)
    add_h1(story, "3. Beiraete")
    add_h2(story, "3.1 Wirtschaftsbeirat")
    add_para(story, "Vorsitz: Prof. Dr. Heinrich Mueller (Universitaet Frankfurt). 12 Mitglieder aus "
             "Wirtschaft und Wissenschaft. Tagt vierteljaehrlich und erstellt Empfehlungen zu wirtschafts- "
             "und finanzpolitischen Fragen. Der Beirat hat beratende Funktion ohne Stimmrecht.")

    add_h2(story, "3.2 Umweltbeirat")
    add_para(story, "Vorsitz: Dr. Sabine Lorenz (Umweltforschungsinstitut Potsdam). 9 Mitglieder. "
             "Beratet den Vorstand in Fragen der Klima- und Umweltpolitik. Erstellt jaehrlich ein "
             "Klimapolitisches Gutachten.")

    add_h2(story, "3.3 Integrationsbeirat")
    add_para(story, "Vorsitz: Fatima Al-Rashid. 8 Mitglieder mit Migrationshintergrund. Beratet zu "
             "Integrations- und Teilhabefragen.")

    add_h1(story, "4. Ausschuesse")
    add_bullet(story, "Satzungsausschuss: 5 Mitglieder, Vorsitz Rechtsanwalt Thomas Weber")
    add_bullet(story, "Finanzausschuss: 4 Mitglieder, Vorsitz Lisa Hartmann")
    add_bullet(story, "Schiedsgericht: 3 Richter, Vorsitz Dr. Juergen Kessler (Richter a.D.)")
    add_bullet(story, "Programmkommission: 7 Mitglieder, Vorsitz Dr. Maria Schneider")
    add_bullet(story, "Wahlkampfkommission: 6 Mitglieder, Vorsitz Markus Brenner")

    add_h1(story, "5. Landesverbaende")
    add_para(story, "Die Partei ist in allen 16 Bundeslaendern mit eigenstaendigen Landesverbaenden vertreten. "
             "Die staerksten Verbaende sind NRW (12.400 Mitglieder), Bayern (9.800), Baden-Wuerttemberg (8.600) "
             "und Niedersachsen (7.200). Insgesamt hat die Partei 78.500 Mitglieder bundesweit (Stand: Januar 2026).")


def mitgliederordnung(story):
    add_para(story, "Gueltig ab 1. Januar 2026 | Beschlossen am 22. November 2025")

    add_h1(story, "Artikel 1: Rechte der Mitglieder")
    add_para(story, "Jedes Mitglied hat das Recht auf: Teilnahme an allen Versammlungen und Veranstaltungen, "
             "aktives und passives Wahlrecht ab Vollendung des 18. Lebensjahrs, Antragsrecht in allen Gremien, "
             "Einsicht in die Protokolle der Vorstandssitzungen (nach Schwurzung vertraulicher Passagen), "
             "kostenlose Teilnahme an Schulungen und Seminaren, Nutzung der parteiinternen Infrastruktur "
             "einschliesslich Bueroraeume und Veranstaltungstechnik.")

    add_h1(story, "Artikel 2: Pflichten der Mitglieder")
    add_para(story, "Die Mitglieder sind verpflichtet: die Satzung und Beschluesse der Organe zu beachten, "
             "die Beitraege puenktlich zu entrichten, die Grundwerte der Partei zu achten und zu foerdern, "
             "vertrauliche Informationen nicht an Dritte weiterzugeben, bei innerparteilichen Konflikten "
             "den Schlichtungsweg zu beschreiten. Verstoesse koennen Ordnungsmassnahmen bis hin zum "
             "Ausschluss nach sich ziehen.")

    add_page_break(story)
    add_h1(story, "Artikel 3: Mitgliedsbeitraege")
    add_para(story, "Der Monatsbeitrag betraegt: Regulaer 15 Euro, Ermaessigt (Studierende, Auszubildende, "
             "Arbeitslose) 5 Euro, Foerdermitgliedschaft ab 25 Euro. Der Jahresbeitrag ist zum 1. Februar "
             "des laufenden Jahres faellig. Bei Zahlungsverzug von mehr als 3 Monaten ruht die Mitgliedschaft. "
             "Beitragsbefreiung kann auf Antrag beim Schatzmeister gewaehrt werden. Die Beitragshoehe "
             "wird jaehrlich von der Mitgliederversammlung ueberprueft.")

    add_h1(story, "Artikel 4: Aufnahmeverfahren")
    add_para(story, "Der Aufnahmeantrag kann schriftlich oder online ueber das Mitgliederportal gestellt werden. "
             "Erforderliche Unterlagen: Personalausweis-Kopie, ausgefuellter Aufnahmeantrag, SEPA-Lastschriftmandat. "
             "Der zustaendige Ortsverband prueft den Antrag und gibt eine Empfehlung ab. Der Vorstand entscheidet "
             "innerhalb von 4 Wochen. Bei Ablehnung ist Widerspruch beim Schiedsgericht moeglich. "
             "Neue Mitglieder erhalten ein Willkommenspaket und werden zum naechsten Onboarding-Termin eingeladen.")

    add_h1(story, "Artikel 5: Austritt und Ausschluss")
    add_para(story, "Der Austritt ist jederzeit moeglich mit einer Kuendigungsfrist von 3 Monaten zum Quartalsende. "
             "Die Kuendigung muss schriftlich erfolgen. Bei Vorliegen schwerwiegender Gruende (Verstoss gegen "
             "die freiheitlich-demokratische Grundordnung, nachhaltiger Satzungsverstoss, Schaedigung des "
             "Ansehens der Partei) kann ein Ausschlussverfahren eingeleitet werden. Die Entscheidung trifft "
             "das Schiedsgericht nach Anhoerung des Betroffenen.")


def koalitionsvertrag_entwurf(story):
    add_para(story, "ENTWURF - Vertraulich | Muster-Verhandlungspapier | Stand: Maerz 2026")

    add_h1(story, "Praeambel")
    add_para(story, "Die unterzeichnenden Parteien vereinbaren fuer die Legislaturperiode 2026-2030 "
             "die folgende Zusammenarbeit auf Bundesebene. Grundlage ist das gemeinsame Ziel, Deutschland "
             "sozial gerechter, oekologisch nachhaltiger und wirtschaftlich staerker zu gestalten. "
             "Die Koalitionspartner verpflichten sich zu vertrauensvoller Zusammenarbeit und regelmaessigem "
             "Austausch im Koalitionsausschuss, der mindestens monatlich tagt.")

    add_h1(story, "Kapitel 1: Wirtschaft und Finanzen")
    add_para(story, "Kompromiss zur Steuerpolitik: Der Spitzensteuersatz wird auf 47% angehoben (Forderung "
             "DZP: 49%, Forderung Koalitionspartner: 45%). Der Grundfreibetrag steigt auf 12.500 Euro. "
             "Die Unternehmenssteuer bleibt unveraendert. Ein Investitionsprogramm von 100 Mrd. Euro "
             "wird aufgelegt, finanziert durch gruene Bundesanleihen. Die Schuldenbremse wird reformiert: "
             "Investitionen in Klimaschutz und Digitalisierung werden von der Schuldenregel ausgenommen.")

    add_page_break(story)
    add_h1(story, "Kapitel 2: Klima und Energie")
    add_para(story, "Kompromiss zum Kohleausstieg: Vorgezogener Ausstieg bis 2032 (Forderung DZP: 2030, "
             "Forderung Partner: 2035). Strukturhilfen fuer betroffene Regionen von 20 Mrd. Euro. "
             "Ausbau erneuerbarer Energien: 80% bis 2032. CO2-Preis steigt auf 130 Euro/Tonne bis 2028. "
             "Klimageld von 150 Euro pro Person ab 2027.")

    add_h1(story, "Kapitel 3: Soziales und Arbeit")
    add_para(story, "Der Mindestlohn wird auf 15 Euro pro Stunde angehoben. Die Minijob-Grenze steigt "
             "auf 600 Euro. Das Buergergeld wird um 12% erhoeht und regelmaessig an die Inflation angepasst. "
             "Das Rentenniveau wird auf 49% stabilisiert (Kompromiss: DZP forderte 50%, Partner 48%). "
             "Ein Rechtsanspruch auf Ganztagsbetreuung fuer Grundschulkinder wird bis 2028 umgesetzt.")

    add_h1(story, "Kapitel 4: Ressortverteilung")
    add_para(story, "DZP erhaelt: Umweltministerium, Arbeitsministerium, Gesundheitsministerium, "
             "Bildungsministerium. Koalitionspartner erhaelt: Finanzministerium, Wirtschaftsministerium, "
             "Verteidigungsministerium, Innenministerium. Gemeinsam besetzt: Auswaertiges Amt (Rotation). "
             "Der Bundeskanzler wird von der staerksten Fraktion gestellt.")

    add_page_break(story)
    add_h1(story, "Kapitel 5: Streitbeilegung")
    add_para(story, "Bei Meinungsverschiedenheiten wird zunaechst auf Arbeitsebene eine Loesung gesucht. "
             "Gelingt dies nicht, entscheidet der Koalitionsausschuss, bestehend aus je 4 Vertretern "
             "beider Parteien. Bei Abstimmungen im Bundestag gilt Koalitionsdisziplin; Abweichungen "
             "sind nur bei Gewissensentscheidungen zulaessig und muessen vorab angekuendigt werden.")


# ==============================================================================
# KATEGORIE 2: Interne Prozesse
# ==============================================================================

def prozess_antrag_stellen(story):
    add_para(story, "Verfahrensordnung | Version 3.1 | Gueltig ab 1. Januar 2026")

    add_h1(story, "1. Antragsberechtigte")
    add_para(story, "Jedes ordentliche Mitglied kann Antraege stellen. Darueber hinaus sind antragsberechtigt: "
             "Ortsverbaende, Kreisverbende, Landesverbaende, der Vorstand, Arbeitsgemeinschaften mit "
             "mindestens 10 Mitgliedern sowie der Parteirat. Foerdermitglieder haben kein Antragsrecht, "
             "koennen aber Anregungen ueber ihren Ortsverband einbringen.")

    add_h1(story, "2. Fristen")
    add_para(story, "Es gelten folgende Fristen: 14 Tage Vorlauf fuer ordentliche Antraege, 48 Stunden fuer "
             "Dringlichkeitsantraege. Ordentliche Antraege muessen schriftlich beim Vorstand eingereicht werden "
             "und werden auf die Tagesordnung der naechsten Sitzung gesetzt. Dringlichkeitsantraege benoetigen "
             "die Unterstuetzung von mindestens 5 Mitgliedern oder einem Kreisverband und muessen begruendet "
             "werden, warum die regulaere Frist nicht eingehalten werden kann.")

    add_h1(story, "3. Formale Anforderungen")
    add_para(story, "Jeder Antrag muss enthalten: Titel des Antrags, Name und Mitgliedsnummer des Antragstellers, "
             "Antragstext mit konkretem Beschlussvorschlag, Begruendung (mindestens 200 Worte), "
             "gegebenenfalls Finanzierungsvorschlag bei kostenwirksamen Antraegen. Antraege ohne "
             "vollstaendige Angaben werden zur Nachbesserung zurueckgewiesen. Die Geschaeftsstelle "
             "prueft die formale Richtigkeit innerhalb von 3 Werktagen.")

    add_page_break(story)
    add_h1(story, "4. Abstimmungsverfahren")
    add_para(story, "Ueber Antraege wird grundsaetzlich offen abgestimmt. Eine geheime Abstimmung findet statt, "
             "wenn mindestens 20% der anwesenden stimmberechtigten Mitglieder dies verlangen. "
             "Fuer die Annahme eines Antrags genuegt die einfache Mehrheit der abgegebenen gueltigen Stimmen. "
             "Satzungsaendernde Antraege benoetigen eine 2/3-Mehrheit. Stimmenthaltungen werden bei der "
             "Berechnung der Mehrheit nicht mitgezaehlt. Bei Stimmengleichheit gilt ein Antrag als abgelehnt. "
             "Aenderungsantraege werden vor dem Hauptantrag abgestimmt.")

    add_h1(story, "5. Behandlung und Nachverfolgung")
    add_para(story, "Angenommene Antraege werden vom Vorstand mit einem Verantwortlichen und einer Frist "
             "versehen. Der Umsetzungsstatus wird auf jeder Vorstandssitzung ueberparaft. Quartalsgericht "
             "ueber den Stand der Antragsumsetzung werden an alle Mitglieder versandt. Abgelehnte Antraege "
             "koennen fruehestens nach 6 Monaten erneut eingebracht werden, es sei denn, wesentlich "
             "neue Sachverhalte liegen vor.")


def prozess_veranstaltung_organisieren(story):
    add_para(story, "Organisationsleitfaden | Version 2.0 | Geschaeftsstelle der DZP")

    add_h1(story, "5-Schritte-Checkliste fuer Mitgliederversammlungen")

    add_h2(story, "Schritt 1: Planung (8-6 Wochen vorher)")
    add_bullet(story, "Termin festlegen unter Beruecksichtigung von Feiertagen und Parallelveranstaltungen")
    add_bullet(story, "Veranstaltungsort buchen: Kapazitaet mindestens 120% der erwarteten Teilnehmer")
    add_bullet(story, "Budget erstellen: Raummiete, Catering, Technik, Druckmaterial")
    add_bullet(story, "Tagesordnung mit dem Vorstand abstimmen")
    add_bullet(story, "Verantwortlichkeiten im Organisationsteam verteilen (mindestens 4 Personen)")

    add_h2(story, "Schritt 2: Einladung (6 Wochen vorher)")
    add_bullet(story, "Formelle Einladung mit Tagesordnung per Post und E-Mail an alle Mitglieder")
    add_bullet(story, "Satzungsgemaesse Ladungsfrist von 6 Wochen beachten")
    add_bullet(story, "Antraege und Unterlagen beilegen")
    add_bullet(story, "Rueckmeldung bis 2 Wochen vorher erbitten")

    add_page_break(story)
    add_h2(story, "Schritt 3: Vorbereitung (2 Wochen vorher)")
    add_bullet(story, "Anmeldungen auswerten, Namensschilder erstellen")
    add_bullet(story, "Technik bestellen: Mikrofon, Beamer, Flipcharts, Abstimmungstechnik")
    add_bullet(story, "Catering beauftragen: vegetarisch/vegan-Option sicherstellen")
    add_bullet(story, "Pressemitteilung vorbereiten, Fotografen organisieren")
    add_bullet(story, "Sitzungsleitung, Protokollfuehrung und Wahlleitung festlegen")

    add_h2(story, "Schritt 4: Durchfuehrung (Tag der Veranstaltung)")
    add_bullet(story, "Aufbau ab 3 Stunden vor Beginn: Bestuhlung, Technik, Registrierung")
    add_bullet(story, "Anwesenheitsliste fuehren (wichtig fuer Beschlussfaehigkeit)")
    add_bullet(story, "Beschlussfaehigkeit feststellen: mindestens 25% der Mitglieder oder 50 Personen")
    add_bullet(story, "Protokoll fuehren mit allen Abstimmungsergebnissen")
    add_bullet(story, "Veranstaltung dokumentieren (Fotos nur mit Einwilligung)")

    add_h2(story, "Schritt 5: Nachbereitung (bis 2 Wochen danach)")
    add_bullet(story, "Protokoll erstellen und innerhalb von 5 Werktagen versenden")
    add_bullet(story, "Pressemitteilung mit Ergebnissen versenden")
    add_bullet(story, "Feedback der Teilnehmer einholen (Online-Umfrage)")
    add_bullet(story, "Rechnungen begleichen, Budgetabrechnung erstellen")
    add_bullet(story, "Beschluesse in das Antragsverfolgungssystem einpflegen")


def prozess_pressemitteilung(story):
    add_para(story, "Workflow-Handbuch | Pressestelle der DZP | Version 1.4 | Februar 2026")

    add_h1(story, "1. Workflow-Ueberblick")
    add_para(story, "Jede Pressemitteilung durchlaeuft einen definierten Freigabeprozess, der Qualitaet "
             "und Konsistenz der externen Kommunikation sicherstellt. Die Gesamtdurchlaufzeit betraegt "
             "im Regelfall 24 Stunden, im Eilverfahren 4 Stunden.")

    add_h1(story, "2. Freigabestufen")
    add_h2(story, "Stufe 1: Entwurf (Referent/in)")
    add_para(story, "Der zustaendige Fachreferent erstellt den Entwurf nach der Vorlage PM-Template-2026. "
             "Maximale Laenge: 400 Worte. Pflichtbestandteile: Ueberschrift, Lead, Zitat, Kontakt.")
    add_h2(story, "Stufe 2: Inhaltliche Pruefung (Fachpolitischer Sprecher)")
    add_para(story, "Der fachpolitische Sprecher prueft inhaltliche Korrektheit und politische Einordnung. "
             "Aenderungswuensche werden im Redaktionssystem dokumentiert. Frist: 4 Stunden.")
    add_h2(story, "Stufe 3: Kommunikative Freigabe (Pressesprecher Markus Brenner)")
    add_para(story, "Der Pressesprecher prueft Tonalitaet, Aktualitaetsbezug und Nachrichtenwert. "
             "Finale redaktionelle Anpassungen werden vorgenommen. Frist: 2 Stunden.")
    add_h2(story, "Stufe 4: Politische Freigabe (Vorsitzende oder Stellvertreter)")
    add_para(story, "Bei politisch sensiblen Themen gibt die Vorsitzende Dr. Maria Schneider oder der "
             "Stellvertreter Thomas Weber die finale Freigabe. Frist: 2 Stunden.")

    add_page_break(story)
    add_h1(story, "3. Verteiler")
    add_para(story, "Die Pressemitteilungen werden ueber folgende Kanaele verbreitet: "
             "Nachrichtenagenturen (dpa, AFP, Reuters), ueberregionale Tageszeitungen (Sueddeutsche, FAZ, "
             "Die Zeit, Spiegel, taz), regionale Medien nach Relevanz, Online-Redaktionen, "
             "Parteieigene Kanaele (Website, Social Media, Newsletter).")
    add_para(story, "Der Presserverteiler umfasst 847 Kontakte und wird quartalsgericht aktualisiert. "
             "Fuer die Versendung wird das Tool 'PressPort Pro' genutzt.")

    add_h1(story, "4. Sonderverfahren: Eilmeldungen")
    add_para(story, "Bei breaking news oder Krisensituationen kann der Pressesprecher in Abstimmung mit "
             "der Vorsitzenden eine Pressemitteilung im Schnellverfahren (1 Stunde) freigeben. "
             "In diesem Fall entfaellt Stufe 2. Die nachtraegliche Information des fachpolitischen "
             "Sprechers muss innerhalb von 24 Stunden erfolgen.")


def prozess_reisekostenabrechnung(story):
    add_para(story, "Abrechnungsleitfaden | Finanzverwaltung | Version 2.2 | Januar 2026")

    add_h1(story, "1. Erstattungsfaehige Kosten")
    add_para(story, "Folgende Kosten werden erstattet: Bahnfahrten 2. Klasse (1. Klasse nur mit "
             "Vorabgenehmigung des Schatzmeisters), Fluge in Economy-Klasse bei Strecken ueber 600 km, "
             "Kilometerpauschale bei PKW-Nutzung: 0,30 Euro/km, Uebernachtungskosten bis maximal "
             "120 Euro pro Nacht (in Muenchen und Frankfurt bis 150 Euro), Verpflegungspauschalen: "
             "14 Euro bei mehr als 8 Stunden Abwesenheit, 28 Euro bei mehr als 24 Stunden. "
             "Taxi-Kosten werden nur bei Abend-/Nachtfahrten oder schweren Gepaeck erstattet.")

    add_h1(story, "2. Einreichungsverfahren")
    add_para(story, "Die Reisekostenabrechnung ist innerhalb von 4 Wochen nach Reiseende einzureichen. "
             "Folgende Unterlagen sind beizufuegen: Ausgefuelltes Formular RK-2026, Originalbelege "
             "fuer alle Ausgaben ueber 10 Euro, Bahntickets oder Buchungsbestaetigung, "
             "Hotelrechnungen mit Einzelnachweis, Programm oder Einladung der Veranstaltung. "
             "Die Einreichung erfolgt ueber das Online-Portal oder postalisch an die Geschaeftsstelle.")

    add_page_break(story)
    add_h1(story, "3. Genehmigung und Auszahlung")
    add_para(story, "Reisekosten bis 500 Euro werden von der Geschaeftsfuehrung genehmigt. Kosten ueber "
             "500 Euro benoetigen die Genehmigung des Schatzmeisters Lisa Hartmann. Die Auszahlung erfolgt "
             "innerhalb von 14 Werktagen nach Genehmigung per Ueberweisung auf das hinterlegte Konto. "
             "Bei unvollstaendigen Unterlagen wird die Abrechnung zur Nachbesserung zurueckgesandt.")

    add_h1(story, "4. Besondere Regelungen fuer Ehrenamtliche")
    add_para(story, "Ehrenamtliche Mitarbeiter koennen zusaetzlich eine Aufwandspauschale von bis zu "
             "840 Euro jaehrlich steuerfrei erhalten (Ehrenamtspauschale nach Paragraf 3 Nr. 26a EStG). "
             "Fuer Uebungsleiter gilt die erhoehte Pauschale von 3.000 Euro jaehrlich. "
             "Die Kombination von Reisekostenerstattung und Pauschale ist zulaessig.")


def prozess_mitgliederverwaltung(story):
    add_para(story, "Verwaltungshandbuch | Mitgliederservice | Version 4.0 | Februar 2026")

    add_h1(story, "1. Beitragsverwaltung")
    add_para(story, "Die Mitgliedsbeitraege werden per SEPA-Lastschrift eingezogen, in der Regel am "
             "15. des Monats. Die Beitragsstafel: Regulaer 15 Euro/Monat, Ermaessigt 5 Euro/Monat, "
             "Foerdermitglieder ab 25 Euro/Monat. Bei fehlgeschlagenen Lastschriften erfolgt ein "
             "zweiter Einzugsversuch nach 7 Tagen. Die anfallenden Bankgebuehren von 3,50 Euro werden "
             "dem Mitglied in Rechnung gestellt. Nach 3 aufeinanderfolgenden Fehlversuchen wird das "
             "Mitglied schriftlich gemahnt.")

    add_h1(story, "2. Ein- und Austritte")
    add_para(story, "Neuaufnahmen werden im Mitgliederverwaltungssystem 'VereinsManager Pro' erfasst. "
             "Pflichtfelder: Name, Geburtsdatum, Anschrift, E-Mail, Telefon, Bankverbindung. "
             "Die Mitgliedsnummer wird automatisch vergeben (Format: DZP-JJJJ-NNNNN). "
             "Beim Austritt wird das Mitglied auf 'inaktiv' gesetzt, Daten werden nach Ablauf "
             "der gesetzlichen Aufbewahrungsfristen (10 Jahre fuer Finanzdaten) geloescht.")

    add_page_break(story)
    add_h1(story, "3. Datenschutz (DSGVO)")
    add_para(story, "Die Verarbeitung personenbezogener Daten erfolgt auf Grundlage von Art. 6 Abs. 1 "
             "lit. b DSGVO (Vertragserfullung/Mitgliedschaft). Jedes Mitglied erhaelt bei Aufnahme eine "
             "Datenschutzerklaerung. Die Daten werden auf Servern in Deutschland gespeichert "
             "(Rechenzentrum Frankfurt, ISO 27001 zertifiziert). Zugriff haben nur autorisierte "
             "Mitarbeiter der Geschaeftsstelle und der zustaendige Ortsverband. "
             "Datenschutzbeauftragter: Dr. Frank Meister, erreichbar unter datenschutz@dzp-partei.de. "
             "Jedes Mitglied hat das Recht auf Auskunft, Berichtigung und Loeschung seiner Daten.")

    add_h1(story, "4. Jahresmeldungen")
    add_para(story, "Zum 31. Dezember jeden Jahres wird eine Mitgliedersstatistik erstellt mit: "
             "Gesamtmitgliederzahl, Neuzugaenge, Austritte, Altersstruktur, Geschlechterverteilung, "
             "regionale Verteilung. Diese Statistik wird dem Vorstand und den Landesverbaenden "
             "zur Verfuegung gestellt und dient als Grundlage fuer die Parteifinanzierung.")


def prozess_beschlussverfolgung(story):
    add_para(story, "Tracking-Handbuch | Geschaeftsstelle | Version 1.2 | Maerz 2026")

    add_h1(story, "1. Systematik des Beschluss-Trackings")
    add_para(story, "Jeder gefasste Beschluss erhaelt eine eindeutige Beschlussnummer (Format: B-JJJJ-NNN), "
             "wird in der zentralen Beschlussdatenbank erfasst und einem Verantwortlichen zugewiesen. "
             "Die Geschaeftsstelle fuehrt die Datenbank und ueberwacht die Einhaltung der Fristen. "
             "Aktuell befinden sich 247 aktive Beschluesse im System (Stand: Februar 2026).")

    add_h1(story, "2. Status-Kategorien")
    add_bullet(story, "Offen: Beschluss gefasst, Umsetzung noch nicht begonnen")
    add_bullet(story, "In Bearbeitung: Umsetzung laeuft, Verantwortlicher benannt")
    add_bullet(story, "Teilweise umgesetzt: Einzelne Massnahmen abgeschlossen")
    add_bullet(story, "Umgesetzt: Alle Massnahmen abgeschlossen, Erfolgskontrolle durchgefuehrt")
    add_bullet(story, "Zurueckgestellt: Umsetzung aus definierten Gruenden verschoben")
    add_bullet(story, "Aufgehoben: Beschluss durch neuen Beschluss ersetzt oder widerrufen")

    add_page_break(story)
    add_h1(story, "3. Reporting-Zyklus")
    add_para(story, "Monatlich: Kurzbericht des Verantwortlichen an die Geschaeftsstelle (Status, "
             "naechste Schritte, eventuelle Hindernisse). Quartalsgericht: Zusammenfassender Bericht "
             "an den Vorstand mit Ampelsystem (gruen/gelb/rot). Jaehrlich: Umfassender "
             "Umsetzungsbericht an die Mitgliederversammlung mit Statistiken und Empfehlungen.")

    add_h1(story, "4. Eskalationsverfahren")
    add_para(story, "Wird eine Umsetzungsfrist um mehr als 4 Wochen ueberschritten, informiert die "
             "Geschaeftsstelle den Vorstand. Der Vorstand kann: eine Fristverlaengerung gewaehren, "
             "den Verantwortlichen wechseln, zusaetzliche Ressourcen bereitstellen oder den Beschluss "
             "zur erneuten Beratung auf die Tagesordnung setzen. Bei wiederholter Nichtumsetzung "
             "wird der Sachverhalt der Mitgliederversammlung zur Kenntnis gebracht.")


def leitfaden_ehrenamtliche(story):
    add_para(story, "Handbuch Ehrenamtskoordination | Bundesgeschaeftsstelle | Januar 2026")

    add_h1(story, "1. Bedeutung des Ehrenamts")
    add_para(story, "Ueber 12.000 ehrenamtliche Mitarbeiterinnen und Mitarbeiter bilden das Rueckgrat "
             "unserer Parteiarbeit. Ohne ihr Engagement waere die Arbeit in den 2.340 Ortsverbaenden, "
             "bei Wahlkaempfen und Veranstaltungen nicht moeglich. Dieses Handbuch dient als Leitfaden "
             "fuer alle, die Ehrenamtliche koordinieren und unterstuetzen.")

    add_h1(story, "2. Onboarding neuer Ehrenamtlicher")
    add_bullet(story, "Erstgespraech mit dem Ehrenamtskoordinator des Ortsverbands innerhalb von 2 Wochen")
    add_bullet(story, "Vorstellung der Taetigkeitsfelder: Wahlkampf, Veranstaltungen, Buero, Social Media")
    add_bullet(story, "Einweisung in interne Kommunikationstools (Slack, E-Mail-Verteiler)")
    add_bullet(story, "Zuweisung eines erfahrenen Paten/einer erfahrenen Patin fuer 3 Monate")
    add_bullet(story, "Teilnahme am naechsten Einfuehrungsseminar (quartalsgericht)")

    add_page_break(story)
    add_h1(story, "3. Koordination und Einsatzplanung")
    add_para(story, "Die Einsatzplanung erfolgt ueber das Tool 'VolunteerHub'. Jeder Ehrenamtliche kann "
             "seine Verfuegbarkeiten dort eintragen. Die Koordinatoren erstellen auf dieser Basis "
             "Einsatzplaene fuer Veranstaltungen und Aktionen. Grundsaetze: Niemand soll mehr als "
             "8 Stunden pro Woche ehrenamtlich taetig sein. Zwischen zwei Einsaetzen muessen mindestens "
             "48 Stunden liegen. Besondere Qualifikationen werden im Profil vermerkt.")

    add_h1(story, "4. Wertschaetzung und Anerkennung")
    add_para(story, "Wertschaetzung ist kein 'nice to have', sondern zentral fuer die Bindung Ehrenamtlicher. "
             "Massnahmen: Persoenliche Dankesbriefe nach groesseren Einsaetzen, jaehrliches Ehrenamtsfest "
             "(Budget: 5.000 Euro pro Landesverband), Ehrung langjhriger Ehrenamtlicher auf dem Parteitag "
             "(ab 5, 10, 25 Jahren), kostenlose Weiterbildungsangebote, Ehrenamtskarte mit Verguenstigungen "
             "bei Partnerorganisationen. Die Ehrenamtskoordinatorin auf Bundesebene ist Frau Julia Bergmann "
             "(ehrenamt@dzp-partei.de, Tel. 030-1234567-40).")


# ==============================================================================
# KATEGORIE 3: Externe Kommunikation
# ==============================================================================

def leitfaden_social_media(story):
    add_para(story, "Social-Media-Richtlinien | Pressestelle | Version 3.0 | Januar 2026")

    add_h1(story, "1. Grundsaetze der Social-Media-Kommunikation")
    add_para(story, "Unsere Social-Media-Praesenz vertritt die Werte und Positionen der Partei. Jeder Post "
             "muss sachlich korrekt, respektvoll und inklusiv formuliert sein. Wir kommunizieren auf "
             "Augenhoehe und vermeiden herablassenden oder polemischen Ton. Humor ist erlaubt, darf "
             "aber nie auf Kosten von Minderheiten gehen. Alle offiziellen Accounts werden zentral "
             "ueber das Social-Media-Team betreut.")

    add_h1(story, "2. Do's")
    add_bullet(story, "Aktuelle politische Themen zeitnah kommentieren (innerhalb von 2 Stunden)")
    add_bullet(story, "Eigene Positionen klar und verstaendlich darstellen")
    add_bullet(story, "Auf Kommentare und Fragen innerhalb von 4 Stunden antworten")
    add_bullet(story, "Erfolge und Veranstaltungen mit Bildern und Videos dokumentieren")
    add_bullet(story, "Fachbegriffe in einfacher Sprache erklaeren")
    add_bullet(story, "Quellen verlinken bei Faktenbehauptungen")

    add_h1(story, "3. Don'ts")
    add_bullet(story, "Keine persoenlichen Angriffe auf politische Gegner")
    add_bullet(story, "Keine unverifizierten Informationen teilen")
    add_bullet(story, "Keine Bilder ohne Urheberrechtsnachweis verwenden")
    add_bullet(story, "Keine internen Diskussionen oder Konflikte oeffentlich machen")
    add_bullet(story, "Keine automatisierten Bots oder gekauften Follower einsetzen")

    add_page_break(story)
    add_h1(story, "4. Tonalitaet nach Plattform")
    add_para(story, "Instagram: Inspirierend, visuell, persoenlich. Hashtags max. 10 pro Post. "
             "TikTok: Locker, kreativ, nahbar. Trends aufgreifen. "
             "X/Twitter: Pointiert, aktuell, dialogorientiert. "
             "Facebook: Ausfuehrlicher, community-orientiert, lokal. "
             "LinkedIn: Professionell, politisch-analytisch.")

    add_h1(story, "5. Reaktionszeiten")
    add_para(story, "Standard-Kommentare: Antwort innerhalb von 4 Stunden waehrend der Geschaeftszeiten. "
             "Presseanfragen ueber Social Media: Weiterleitung an Pressestelle innerhalb von 1 Stunde. "
             "Krisensituationen und Shitstorms: Reaktionszeit maximal 30 Minuten. Dazu wird das "
             "Social-Media-Team durch den diensthabenden Krisenkommunikator verstaerkt. "
             "Am Wochenende und an Feiertagen ist ein Bereitschaftsdienst eingerichtet (Erreichbarkeit "
             "ueber die Notfall-Hotline 030-1234567-99).")


def krisenhandbuch_shitstorm(story):
    add_para(story, "Krisenhandbuch | Streng Vertraulich | Pressestelle | Version 2.1 | Februar 2026")

    add_h1(story, "Ueberblick")
    add_para(story, "Dieses Handbuch definiert das Vorgehen bei Social-Media-Krisen und Shitstorms. "
             "Es gilt fuer alle offiziellen Kanaele der Partei und wird vom Pressesprecher Markus Brenner "
             "verantwortet. Jedes Mitglied des Kommunikationsteams muss dieses Handbuch kennen und "
             "jaehrlich an einer Krisenuebung teilnehmen. Letzte Uebung: 15. Januar 2026.")

    add_h1(story, "Die 4 Eskalationsstufen")

    add_h2(story, "Eskalationsstufe 1: Einzelkritik (Gruen)")
    add_para(story, "Beschreibung: Vereinzelte kritische Kommentare oder negative Posts von Einzelpersonen. "
             "Weniger als 50 negative Interaktionen innerhalb von 2 Stunden. "
             "Zustaendig: Social-Media-Team (diensthabende/r Redakteur/in). "
             "Massnahmen: Sachliche Antwort auf den konkreten Vorwurf, keine Eskalation. "
             "Dokumentation im Monitoring-Tool. Keine Meldung an den Vorstand erforderlich.")

    add_h2(story, "Eskalationsstufe 2: Wachsende Kritik (Gelb)")
    add_para(story, "Beschreibung: Mehrere kritische Posts, Thema wird von kleineren Accounts aufgegriffen. "
             "50-500 negative Interaktionen innerhalb von 2 Stunden. Erwaehnung in einzelnen Online-Medien. "
             "Zustaendig: Social-Media-Team plus Pressesprecher. "
             "Massnahmen: Abstimmung einer einheitlichen Sprachregelung, proaktive Kommunikation, "
             "Monitoring alle 30 Minuten. Information an den Vorstand.")

    add_page_break(story)
    add_h2(story, "Eskalationsstufe 3: Shitstorm (Orange)")
    add_para(story, "Beschreibung: Massiver negativer Trend, Hashtags trenden, klassische Medien berichten. "
             "Mehr als 500 negative Interaktionen pro Stunde. Gegnerische Parteien greifen das Thema auf. "
             "Zustaendig: Krisenteam wird aktiviert (Pressesprecher, Vorsitzende, Fachreferent, Justiziarin). "
             "Massnahmen: Krisenmeeting innerhalb von 1 Stunde, offizielles Statement vorbereiten, "
             "alle geplanten Posts pausieren, Medienanfragen zentral ueber Pressesprecher beantworten. "
             "Ggf. Video-Statement der Vorsitzenden Dr. Maria Schneider.")

    add_h2(story, "Eskalationsstufe 4: Existenzielle Krise (Rot)")
    add_para(story, "Beschreibung: Die Krise bedroht das Ansehen oder den Bestand der Partei. Ruecktrittsforderungen, "
             "massive Medienberichterstattung, Mitgliedsaustritte. Dauer: mehr als 48 Stunden Spitzenbelastung. "
             "Zustaendig: Gesamter Vorstand plus externe Krisenberater (Rahmen-Vertrag mit Agentur Krisenstab GmbH). "
             "Massnahmen: Pressekonferenz innerhalb von 6 Stunden, persoenliches Statement der Vorsitzenden, "
             "taegliche Lageberichte, juristische Pruefung aller Optionen, ggf. personelle Konsequenzen. "
             "Nachbereitung: Krisenevaluation innerhalb von 2 Wochen, Anpassung des Krisenhandbuchs.")

    add_page_break(story)
    add_h1(story, "Reaktionsteam und Kontakte")
    add_para(story, "Krisenstab-Leitung: Markus Brenner (Pressesprecher), Tel. 0170-1234567, erreichbar 24/7. "
             "Stellvertretung: Dr. Claudia Reinhardt, Tel. 0171-2345678. "
             "Justiziarin: Rechtsanwaeltin Karin Stoecker, Tel. 0172-3456789. "
             "Externe Krisenberatung: Krisenstab GmbH, Notfall-Hotline 0800-KRISE00. "
             "IT-Sicherheit (bei Hacking): Stefan Maier, Tel. 0173-4567890.")

    add_h1(story, "Vorlagen")
    add_para(story, "Im Anhang finden sich folgende Vorlagen: Textbaustein 'Wir nehmen die Kritik ernst', "
             "Textbaustein 'Richtigstellung', Textbaustein 'Entschuldigung', Muster-Presseerklaerung, "
             "Checkliste Krisenmeeting, Protokoll-Vorlage Krisenstabssitzung. Alle Vorlagen sind auf "
             "dem internen Server unter K:/Kommunikation/Krisen/Vorlagen/ gespeichert.")


def presseverteiler(story):
    add_para(story, "Presseverteiler | Pressestelle | Letzte Aktualisierung: 1. Maerz 2026 | Vertraulich")

    add_h1(story, "1. Nachrichtenagenturen")
    add_bullet(story, "dpa Deutsche Presse-Agentur: politik@dpa.de, Ansprechpartner Michael Schreiber")
    add_bullet(story, "AFP Agence France-Presse: berlin@afp.com, Ansprechpartnerin Sophie Lambert")
    add_bullet(story, "Reuters: germany.politics@reuters.com, Ansprechpartner James Miller")
    add_bullet(story, "epd Evangelischer Pressedienst: politik@epd.de, Ansprechpartner Hans-Peter Braun")

    add_h1(story, "2. Ueberregionale Tageszeitungen")
    add_h2(story, "Ressort Politik/Innenpolitik")
    add_bullet(story, "Sueddeutsche Zeitung: Ressortleiter Stefan Maier, s.maier@sz.de")
    add_bullet(story, "Frankfurter Allgemeine Zeitung: Korrespondentin Dr. Anna Huber, a.huber@faz.net")
    add_bullet(story, "Die Zeit: Redakteur Jan Wehner, j.wehner@zeit.de")
    add_bullet(story, "taz: Redakteurin Miriam Vogel, m.vogel@taz.de")
    add_bullet(story, "Die Welt: Korrespondent Friedrich Becker, f.becker@welt.de")
    add_bullet(story, "Handelsblatt: Politikchef Lars Koenig, l.koenig@hb.de")

    add_page_break(story)
    add_h1(story, "3. Regionale Medien (Auswahl)")
    add_h2(story, "Nordrhein-Westfalen")
    add_bullet(story, "Koelner Stadtanzeiger: Thomas Richter, t.richter@ksta.de")
    add_bullet(story, "Rheinische Post: Sabine Wolff, s.wolff@rp-online.de")
    add_bullet(story, "Westdeutsche Allgemeine: Martin Scholz, m.scholz@waz.de")

    add_h2(story, "Bayern")
    add_bullet(story, "Muenchner Merkur: Petra Lang, p.lang@merkur.de")
    add_bullet(story, "Nuernberger Nachrichten: Klaus Fischer, k.fischer@nn.de")

    add_h2(story, "Baden-Wuerttemberg")
    add_bullet(story, "Stuttgarter Zeitung: Andrea Bergmann, a.bergmann@stz.de")
    add_bullet(story, "Badische Zeitung: Rolf Hauser, r.hauser@badische-zeitung.de")

    add_h2(story, "Berlin/Brandenburg")
    add_bullet(story, "Tagesspiegel: Katharina Winter, k.winter@tagesspiegel.de")
    add_bullet(story, "Berliner Zeitung: Mohammed Al-Farouq, m.alfarouq@berliner-zeitung.de")

    add_h1(story, "4. TV und Rundfunk")
    add_bullet(story, "ARD Hauptstadtstudio: politikredaktion@ard.de")
    add_bullet(story, "ZDF Hauptstadtstudio: politik@zdf.de")
    add_bullet(story, "Deutschlandfunk: dl.politik@deutschlandfunk.de")
    add_bullet(story, "RTL/ntv: politik@rtl.de")

    add_h1(story, "5. Online-Medien")
    add_bullet(story, "Spiegel Online: redaktion.politik@spiegel.de")
    add_bullet(story, "T-Online: politik@t-online.de")
    add_bullet(story, "The Pioneer: briefing@thepioneer.de")


def corporate_design_manual(story):
    add_para(story, "Corporate Design Manual | Markenidentitaet der DZP | Version 5.0 | Februar 2026")

    add_h1(story, "1. Logo-Richtlinien")
    add_para(story, "Das Logo der Demokratischen Zukunftspartei besteht aus einem stilisierten Horizont-Symbol "
             "und dem Schriftzug 'DZP'. Das Logo darf nicht verzerrt, gedreht oder in nicht-autorisierten "
             "Farben dargestellt werden. Der Mindestabstand (Schutzzone) betraegt die Hoehe des Buchstabens 'D' "
             "in alle Richtungen. Die Mindestgroesse fuer den Druck ist 25 mm Breite, fuer digitale "
             "Anwendungen 120 Pixel Breite. Das Logo ist in folgenden Varianten verfuegbar: "
             "Vollfarbig, Weiss auf dunklem Hintergrund, Schwarz-Weiss fuer Faxe und Stempel.")

    add_h1(story, "2. Farben")
    add_para(story, "Primaerfarbe: DZP-Blau #2c5aa0 (RGB: 44, 90, 160 / CMYK: 86, 56, 0, 0). "
             "Sekundaerfarbe: Signal-Rot #e63946 (RGB: 230, 57, 70 / CMYK: 0, 85, 65, 0). "
             "Akzentfarbe: Grau #4a4a4a (RGB: 74, 74, 74 / CMYK: 0, 0, 0, 75). "
             "Hintergrund: Hellgrau #f5f5f5 und Weiss #ffffff. "
             "Die Primaerfarbe dominiert alle Materialien (mindestens 60% der farbigen Flaeche). "
             "Signal-Rot wird sparsam eingesetzt fuer Hervorhebungen und Call-to-Actions.")

    add_page_break(story)
    add_h1(story, "3. Schriften")
    add_para(story, "Hausschrift Ueberschriften: 'Source Sans Pro Bold'. "
             "Hausschrift Fliesstext: 'Source Sans Pro Regular'. "
             "Alternativschrift (wenn Hausschrift nicht verfuegbar): Arial oder Helvetica. "
             "Web-Schrift: Google Fonts 'Source Sans 3'. "
             "Schriftgroessen: Hauptueberschrift 24pt, Unterueberschrift 18pt, Fliesstext 11pt, "
             "Fussnoten 8pt. Zeilenabstand: 1,4-fach fuer Fliesstext, 1,2-fach fuer Ueberschriften.")

    add_h1(story, "4. Gestaltungsraster")
    add_para(story, "Fuer Drucksachen gilt ein 12-Spalten-Raster mit 5mm Spaltenabstand. "
             "Seitenraender: oben 25mm, unten 20mm, links 20mm, rechts 15mm. "
             "Bilder werden grundsaetzlich randabfallend oder im goldenen Schnitt platziert. "
             "Textbloecke sind linksuundig gesetzt, Flattersatz ist zu bevorzugen.")

    add_h1(story, "5. Anwendungsbeispiele")
    add_para(story, "Briefpapier: Logo oben links, Absenderzeile in 8pt Source Sans Pro, "
             "Adressfeld nach DIN 5008. Visitenkarten: 85x55mm, Logo auf Vorderseite, "
             "Kontaktdaten auf Rueckseite. Plakate: Logo prominent in oberer rechter Ecke, "
             "Hauptaussage in maximal 7 Worten, DZP-Blau als Hintergrund. Flyer: DIN-lang, "
             "6 Seiten, Falz nach innen, Logo auf Titelseite und Rueckseite.")


def leitfaden_offentlichkeitsarbeit(story):
    add_para(story, "Leitfaden Oeffentlichkeitsarbeit | Pressestelle | Version 2.3 | Januar 2026")

    add_h1(story, "1. Grundsaetze der Medienarbeit")
    add_para(story, "Die Oeffentlichkeitsarbeit der DZP verfolgt das Ziel, die Positionen der Partei "
             "verstaendlich und ueberzeugend in der medialen Oeffentlichkeit zu platzieren. "
             "Grundsaetze: Transparenz, Wahrhaftigkeit, Zeitnaehe, Verstaendlichkeit. "
             "Jede externe Kommunikation muss im Einklang mit den beschlossenen Positionen stehen. "
             "Bei Zweifeln ist Ruecksprache mit dem fachpolitischen Sprecher zu halten.")

    add_h1(story, "2. Instrumente der Medienarbeit")
    add_bullet(story, "Pressemitteilungen: 3-5 pro Woche zu aktuellen Themen")
    add_bullet(story, "Pressekonferenzen: Quartalsweise oder anlassbezogen, Einladung 48h vorher")
    add_bullet(story, "Hintergrundgespraeche: Vertrauliche Treffen mit ausgewaehlten Journalisten")
    add_bullet(story, "Interviews: Anfragen werden zentral ueber die Pressestelle koordiniert")
    add_bullet(story, "Gastbeitraege: Vorsitzende oder Fachsprecher in Leitmedien")
    add_bullet(story, "Social Media: Echtzeit-Kommunikation gemaess Social-Media-Leitfaden")

    add_page_break(story)
    add_h1(story, "3. Kampagnen-Planung")
    add_para(story, "Jede Kommunikationskampagne durchlaeuft folgende Phasen: "
             "Phase 1 (Analyse): Ausgangslage, Zielgruppen, Wettbewerb (2 Wochen). "
             "Phase 2 (Strategie): Kernbotschaften, Kanaele, Budget, Timeline (1 Woche). "
             "Phase 3 (Produktion): Texte, Grafiken, Videos, Druckmaterial (2-4 Wochen). "
             "Phase 4 (Rollout): Gestaffelte Veroeffentlichung ueber alle Kanaele (1-4 Wochen). "
             "Phase 5 (Evaluation): Reichweite, Resonanz, Medienecho, Learnings (1 Woche).")

    add_h1(story, "4. Zusammenarbeit mit der Pressestelle")
    add_para(story, "Alle Medienkontakte laufen ueber die Pressestelle (pressestelle@dzp-partei.de, "
             "Tel. 030-1234567-20). Direkte Medienanfragen an einzelne Funktionstraeger sind "
             "unverzueglich an die Pressestelle weiterzuleiten. Interviewtermine werden nur von "
             "der Pressestelle vereinbart. Embargos und Sperrfristen werden strikt eingehalten. "
             "Die Pressestelle ist besetzt: Mo-Fr 8:00-20:00, Sa 10:00-16:00. "
             "Ausserhalb der Dienstzeiten ist der Bereitschaftsdienst erreichbar.")


def datenschutz_kommunikation(story):
    add_para(story, "Datenschutz-Leitfaden fuer die Pressearbeit | DZP | Version 1.1 | Februar 2026")

    add_h1(story, "1. Rechtsgrundlagen")
    add_para(story, "Die Oeffentlichkeitsarbeit muss die Anforderungen der DSGVO, des BDSG und des "
             "Kunsturhebergesetzes (KUG) beachten. Verantwortlich im Sinne des Datenschutzrechts ist "
             "der Bundesvorstand der DZP. Datenschutzbeauftragter: Dr. Frank Meister. "
             "Dieser Leitfaden ergaenzt die allgemeine Datenschutzordnung der Partei.")

    add_h1(story, "2. Fotografien und Videos")
    add_para(story, "Bei allen Veranstaltungen muessen Teilnehmer ueber Foto- und Videoaufnahmen "
             "informiert werden (Aushang am Eingang, muendlicher Hinweis). Fuer die Veroeffentlichung "
             "von Einzelportraets ist eine schriftliche Einwilligung erforderlich (Formular EW-FOTO-01). "
             "Ausnahme: Veranstaltungsfotos mit mehr als 10 erkennbaren Personen gelten als "
             "Versammlungsbilder (Paragraf 23 Abs. 1 Nr. 3 KUG). Fotos mit Minderjaerigen "
             "benoetigen immer die Einwilligung der Erziehungsberechtigten.")

    add_page_break(story)
    add_h1(story, "3. Pressemitteilungen und personenbezogene Daten")
    add_para(story, "In Pressemitteilungen duerfen nur Daten von Personen genannt werden, die "
             "oeffentliche Aemter oder Funktionen wahrnehmen oder ihre Einwilligung gegeben haben. "
             "Private Kontaktdaten (private Telefonnummer, private E-Mail) duerfen nie in "
             "Pressemitteilungen erscheinen. Fuer Zitate gilt: Freigabe durch die zitierte Person "
             "ist zwingend erforderlich, auch bei woertlichen Reden auf oeffentlichen Veranstaltungen.")

    add_h1(story, "4. Newsletter und E-Mail-Kommunikation")
    add_para(story, "Der Versand von Newslettern an Nicht-Mitglieder erfordert ein Double-Opt-In-Verfahren. "
             "Jeder Newsletter muss einen funktionierenden Abmeldelink enthalten. Die Einwilligungen "
             "werden im CRM-System protokolliert und sind mindestens 3 Jahre nach Abmeldung aufzubewahren. "
             "Segmentierung des Verteilers nach Interessen ist zulaessig, Profiling im engeren Sinne "
             "der DSGVO (Art. 22) ist ohne ausdrueckliche Einwilligung unzulaessig.")

    add_h1(story, "5. Social-Media-Datenschutz")
    add_para(story, "Fuer Social-Media-Auftritte gelten besondere Anforderungen: Impressum und "
             "Datenschutzhinweis muessen auf jeder Plattform verlinkt sein. Insights und "
             "Analyse-Tools der Plattformen duerfen genutzt werden, es besteht jedoch gemeinsame "
             "Verantwortlichkeit (Art. 26 DSGVO) mit dem Plattformbetreiber. Custom Audiences "
             "duerfen nur mit Einwilligung der Betroffenen erstellt werden. "
             "Pixel-Tracking auf der Partei-Website erfordert Cookie-Consent.")


# ==============================================================================
# KATEGORIE 4: Schulungsmaterial
# ==============================================================================

def schulung_rhetorik_basics(story):
    add_para(story, "Schulungsunterlagen | Referat Politische Bildung | Dozent: Prof. Dr. Karl Lehmann")

    add_h1(story, "1. Grundlagen der Redetechnik")
    add_para(story, "Eine wirkungsvolle Rede besteht aus drei Elementen: Logos (Sachargument), "
             "Ethos (Glaubwuerdigkeit des Redners) und Pathos (emotionale Ansprache). In der "
             "politischen Kommunikation ist die Verbindung aller drei Elemente entscheidend. "
             "Die ideale Redezeit fuer politische Statements betraegt 3-5 Minuten, "
             "fuer Grundsatzreden 15-20 Minuten. Laengere Reden verlieren die Aufmerksamkeit.")

    add_h1(story, "2. Aufbau einer politischen Rede")
    add_bullet(story, "Einstieg: Persoenliche Anekdote oder aktuelle Bezugnahme (max. 30 Sekunden)")
    add_bullet(story, "Problemdarstellung: Was ist das Problem? Wen betrifft es? (2-3 Minuten)")
    add_bullet(story, "Loesungsvorschlag: Unsere Position und konkrete Massnahmen (3-5 Minuten)")
    add_bullet(story, "Emotionaler Appell: Warum ist jetzt Handeln noetig? (1-2 Minuten)")
    add_bullet(story, "Abschluss: Zusammenfassung in einem praegnanten Satz (30 Sekunden)")

    add_page_break(story)
    add_h1(story, "3. Koerpersprache")
    add_para(story, "Studien zeigen, dass 55% der Wirkung einer Rede auf die Koerpersprache entfaellt, "
             "38% auf die Stimme und nur 7% auf den Inhalt (Mehrabian-Regel). Wichtige Grundsaetze: "
             "Aufrechte Haltung, stabiler Stand mit schulterbreitem Fussabstand, offene Gesten "
             "(Haende auf Brusthhoehe), Blickkontakt mit dem Publikum (5-Sekunden-Regel: "
             "5 Sekunden eine Person anschauen, dann wechseln). Zu vermeiden: Verschraenkte Arme, "
             "Haende in den Taschen, nervoes mit Gegenstaenden spielen.")

    add_h1(story, "4. Stimmtraining")
    add_para(story, "Die Stimme ist das wichtigste Werkzeug des Redners. Uebungen: "
             "Zwerchfellatmung (5 Minuten taeglich), Artikulationsuebungen mit Korken, "
             "Lautstaerke-Modulation (leise fuer Bedeutung, laut fuer Dringlichkeit), "
             "Pausen einsetzen (3 Sekunden nach wichtigen Aussagen lassen diese wirken). "
             "Vor einer wichtigen Rede: 15 Minuten Aufwaermung, warmes Wasser trinken, "
             "Kiefer- und Schultermuskeln lockern. Tipp: Stimme am Vorabend schonen.")

    add_h1(story, "5. Umgang mit Zwischenfragen und Stoerungen")
    add_para(story, "Grundregel: Ruhe bewahren, nie persoenlich werden. Techniken: "
             "Brauchtechnik (Frage aufgreifen und zur eigenen Botschaft zurueckfuehren), "
             "Sandwich-Technik (Zustimmung, eigene Position, positiver Abschluss), "
             "Bei feindseligen Fragen: 'Danke fuer die Frage' und sachlich antworten.")


def schulung_moderation_gremien(story):
    add_para(story, "Moderationsleitfaden | Referat Politische Bildung | Trainerin: Birgit Neumann")

    add_h1(story, "1. Rolle der Moderation")
    add_para(story, "Die Moderation in politischen Gremien hat eine Schluesselrolle fuer produktive "
             "Sitzungen. Der Moderator ist neutral, strukturiert die Diskussion und sorgt fuer "
             "eine ausgewogene Beteiligung aller Anwesenden. Grundprinzipien: Allparteilichkeit, "
             "Transparenz ueber den Prozess, Zeitmanagement, Ergebnisorientierung. "
             "Die Moderation darf keine eigenen inhaltlichen Beitraege einbringen. "
             "Wenn ein Vorstandsmitglied moderiert und sich inhaltlich aeussern moechte, "
             "muss es die Moderation temporaer abgeben.")

    add_h1(story, "2. Vorbereitung einer Sitzung")
    add_bullet(story, "Tagesordnung vorab versenden (mindestens 3 Tage vorher)")
    add_bullet(story, "Zeitrahmen fuer jeden TOP festlegen und kommunizieren")
    add_bullet(story, "Unterlagen und Beschlussvorlagen vorbereiten")
    add_bullet(story, "Raum vorbereiten: U-Form oder Stuhlkreis, keine Frontalbestuhlung")
    add_bullet(story, "Technik pruefen: Mikrofon, Beamer, Flipchart, Timer")

    add_page_break(story)
    add_h1(story, "3. Gespraechsfuehrung waehrend der Sitzung")
    add_para(story, "Techniken fuer eine strukturierte Diskussion: Rednerliste fuehren und strikt "
             "einhalten, Redezeit begrenzen (3 Minuten pro Beitrag in der Aussprache), "
             "Zwischenzeit-Zusammenfassungen ('Wenn ich richtig zusammenfasse, haben wir bisher ''), "
             "Vielpsprecherbremse (nach 2 Beitraegen zum selben TOP hat der Nochbisherredner "
             "Nachrang), Schweigende aktiv einbeziehen ('Frau Mueller, wie sehen Sie das?'). "
             "Bei aufgeheizten Diskussionen: Blitzlicht-Runde, in der jeder einen Satz sagt.")

    add_h1(story, "4. Protokollierung")
    add_para(story, "Das Protokoll wird parallel zur Sitzung gefuehrt und umfasst: Datum, Uhrzeit, "
             "Ort, Teilnehmer, Tagesordnung, wesentliche Diskussionspunkte (keine woertliche "
             "Mitschrift), Beschluesse mit exaktem Wortlaut und Abstimmungsergebnis, "
             "Verantwortlichkeiten und Fristen, naechster Sitzungstermin. "
             "Das Protokoll wird innerhalb von 5 Werktagen versandt. Einwaende sind innerhalb "
             "von 10 Tagen moeglich, danach gilt das Protokoll als genehmigt.")

    add_h1(story, "5. Umgang mit schwierigen Situationen")
    add_para(story, "Dauerredner: Freundlich unterbrechen, auf Rednerliste verweisen. "
             "Persoenliche Angriffe: Sofort unterbrechen, auf Sachlichkeit hinweisen. "
             "Themen-Abschweifer: 'Diesen wichtigen Punkt nehmen wir in den Themenspeicher auf.' "
             "Blockaden: Abstimmung vorschlagen oder Vertagung anbieten. "
             "Emotionale Ausbrueche: Pause vorschlagen, Einzelgespraech anbieten.")


def schulung_konfliktmanagement(story):
    add_para(story, "Schulungsunterlagen | Referat Politische Bildung | Dozent: Dr. Markus Friedemann")

    add_h1(story, "1. Konflikte in politischen Organisationen")
    add_para(story, "Konflikte sind in politischen Organisationen unvermeidlich und nicht grundsaetzlich "
             "negativ. Sie koennen Motor fuer Veraenderung sein, wenn sie konstruktiv bearbeitet werden. "
             "Haeufige Konflikttypen: Sachkonflikte (unterschiedliche Positionen), Beziehungskonflikte "
             "(persoenliche Spannungen), Verteilungskonflikte (Ressourcen, Posten), Wertkonflikte "
             "(grundsaetzliche Ueberzeugungen). In der DZP werden jaehrlich ca. 35 formale "
             "Schlichtungsverfahren durchgefuehrt (Stand 2025).")

    add_h1(story, "2. Mediation als Konfliktloesung")
    add_para(story, "Die Mediation ist ein strukturiertes Verfahren, bei dem ein neutraler Dritter "
             "die Konfliktparteien bei der Erarbeitung einer einvernehmlichen Loesung unterstuetzt. "
             "Phasen der Mediation: 1) Eroeffnung und Regelvereinbarung, 2) Darstellung der Sichtweisen, "
             "3) Konfliktklaerung und Interessenermittlung, 4) Loesungssuche und Verhandlung, "
             "5) Vereinbarung und Abschluss. Die DZP hat 28 ausgebildete Mediatoren in den "
             "Landesverbaenden. Mediationsanfragen richten Sie an schiedsgericht@dzp-partei.de.")

    add_page_break(story)
    add_h1(story, "3. Deeskalationstechniken")
    add_para(story, "Eskalation erkennen: Erhoehte Lautstaerke, persoenliche Vorwuerfe, Koalitionsbildung, "
             "Drohungen, Verweigerung. Deeskalationsstrategien: "
             "Aktives Zuhoeren (Paraphrasieren: 'Wenn ich Sie richtig verstehe, ...'), "
             "Ich-Botschaften statt Du-Vorwuerfe ('Ich empfinde das als unfair' statt 'Sie sind unfair'), "
             "Bedurfnisse hinter Positionen erfragen ('Was ist Ihnen dabei besonders wichtig?'), "
             "Perspektivwechsel anregen ('Wie wuerden Sie reagieren, wenn ...?'), "
             "Metakommunikation ('Ich merke, dass wir uns im Kreis drehen. Koennen wir kurz innehalten?').")

    add_h1(story, "4. Die Harvard-Methode")
    add_para(story, "Das Harvard-Konzept des sachgerechten Verhandelns basiert auf vier Grundsaetzen: "
             "1) Menschen und Probleme getrennt behandeln: Angriff auf das Problem, nicht auf die Person. "
             "2) Auf Interessen konzentrieren, nicht auf Positionen: Hinter jeder Position stehen Beduerfnisse. "
             "3) Entscheidungsmoeglichkeiten zum beiderseitigen Vorteil entwickeln: Kreativer Loesungsraum. "
             "4) Auf der Anwendung neutraler Beurteilungskriterien bestehen: Objektive Masstaebe "
             "wie Gesetze, Praezedenzfaelle oder Expertenmeinungen heranziehen. "
             "Die Harvard-Methode ist besonders geeignet fuer Koalitionsverhandlungen und "
             "innerparteiliche Kompromissfindung.")

    add_h1(story, "5. Praeventive Massnahmen")
    add_para(story, "Konfliktvermeidung beginnt mit guter Kommunikationskultur: Regelmaessige Feedbackrunden "
             "in allen Gremien, transparente Entscheidungsprozesse, klare Zustaendigkeiten und "
             "Verantwortlichkeiten, Fortbildungen fuer alle Funktionstraeger, jaehrliche Teambildungs-"
             "massnahmen auf Orts- und Kreisverbandsebene. Fruehwarnsystem: Die Geschaeftsstelle erfasst "
             "Beschwerden und Konfliktsignale systematisch und meldet Haeufungen an den Vorstand.")


def onboarding_neue_mitglieder(story):
    add_para(story, "Willkommen bei der DZP! | Ihr Wegweiser fuer die ersten Schritte | Ausgabe 2026")

    add_h1(story, "Herzlich willkommen!")
    add_para(story, "Wir freuen uns sehr, Sie als neues Mitglied in der Demokratischen Zukunftspartei "
             "begruessen zu duerfen! Mit Ihrem Beitritt staerken Sie unsere Gemeinschaft und bringen "
             "Ihre Ideen in die politische Arbeit ein. Diese Broschuere gibt Ihnen einen Ueberblick "
             "ueber die wichtigsten Informationen fuer Ihren Start bei der DZP.")

    add_h1(story, "1. Ihre ersten Schritte")
    add_bullet(story, "Melden Sie sich im Mitgliederportal an: portal.dzp-partei.de (Zugangsdaten per E-Mail)")
    add_bullet(story, "Treten Sie dem Slack-Workspace Ihres Ortsverbands bei")
    add_bullet(story, "Besuchen Sie die naechste Ortsverbandssitzung (Termine im Portal)")
    add_bullet(story, "Nehmen Sie am Onboarding-Seminar teil (naechster Termin: 15. April 2026, Berlin)")
    add_bullet(story, "Waehlen Sie ein Themenfeld, das Sie interessiert (Umwelt, Soziales, Wirtschaft, etc.)")

    add_h1(story, "2. Ihre Ansprechpartner")
    add_para(story, "Bundesgeschaeftsstelle: info@dzp-partei.de, Tel. 030-1234567-0. "
             "Mitgliederservice: mitglieder@dzp-partei.de, Tel. 030-1234567-10. "
             "Ihr Ortsverband: Die Kontaktdaten finden Sie im Mitgliederportal unter 'Mein Ortsverband'. "
             "Ihr persoenlicher Pate/Ihre persoenliche Patin: Wird Ihnen innerhalb von 2 Wochen zugewiesen. "
             "Ehrenamtskoordination: ehrenamt@dzp-partei.de, Tel. 030-1234567-40.")

    add_page_break(story)
    add_h1(story, "3. Moeglichkeiten der Mitarbeit")
    add_para(story, "Bei der DZP gibt es viele Wege, sich einzubringen: Teilnahme an Ortsverbaands-"
             "sitzungen und Mitgliederversammlungen, Mitarbeit in Arbeitsgemeinschaften (AG Umwelt, "
             "AG Soziales, AG Digitales, AG Frauen, AG Migration, AG Senioren), Wahlkampfunterstuetzung "
             "(Infostaende, Haustuerwahlkampf, Social-Media), Organisation von Veranstaltungen, "
             "Kandidatur fuer Aemter und Mandate (ab 1 Jahr Mitgliedschaft), "
             "Schulungen besuchen und selbst als Trainer taetig werden.")

    add_h1(story, "4. Wichtige Termine 2026")
    add_bullet(story, "15. April 2026: Onboarding-Seminar fuer neue Mitglieder, Berlin")
    add_bullet(story, "1.-2. Juni 2026: Bundeskongress, Hamburg")
    add_bullet(story, "20. Juni 2026: Sommerfest der Bundesgeschaeftsstelle, Berlin")
    add_bullet(story, "14.-15. September 2026: Parteitag, Leipzig")
    add_bullet(story, "28. September 2026: Bundestagswahl (voraussichtlich)")
    add_bullet(story, "5. Dezember 2026: Jahresabschlussfeier")

    add_h1(story, "5. Nuetzliche Links")
    add_bullet(story, "Partei-Website: www.dzp-partei.de")
    add_bullet(story, "Mitgliederportal: portal.dzp-partei.de")
    add_bullet(story, "Schulungsplattform: lernen.dzp-partei.de")
    add_bullet(story, "Internes Wiki: wiki.dzp-partei.de (VPN erforderlich)")


def schulung_fundraising(story):
    add_para(story, "Schulungsunterlagen Fundraising | Referat Finanzen | Dozentin: Lisa Hartmann")

    add_h1(story, "1. Grundlagen der Parteifinanzierung")
    add_para(story, "Die Finanzierung politischer Parteien in Deutschland unterliegt dem Parteiengesetz "
             "(PartG). Einnahmequellen: Mitgliedsbeitraege (aktuell 14,2 Mio. Euro/Jahr), Spenden "
             "(8,7 Mio. Euro/Jahr), staatliche Teilfinanzierung (12,1 Mio. Euro/Jahr), "
             "Veranstaltungseinnahmen (1,3 Mio. Euro/Jahr). Alle Spenden ueber 10.000 Euro "
             "muessen im Rechenschaftsbericht namentlich aufgefuehrt werden. Anonyme Spenden "
             "ueber 500 Euro sind unzulaessig. Spenden von Unternehmen sind zulaessig, "
             "von auslaendischen Gebern ausserhalb der EU verboten.")

    add_h1(story, "2. Spendenstrategie")
    add_para(story, "Unsere Spendenstrategie setzt auf drei Saeulen: Kleinspender-Basis (Spenden bis 100 Euro, "
             "Zielgruppe: 50.000 Spender), Mittelfeld (100-5.000 Euro, Zielgruppe: 2.000 Spender, "
             "persoenliche Ansprache durch Kreisverband), Grossspender (ab 5.000 Euro, Zielgruppe: "
             "200 Spender, persoenliche Betreuung durch Bundesebene). Wichtig: Keine Gegenleistungen "
             "fuer Spenden zusichern! Transparenz ist oberstes Gebot.")

    add_page_break(story)
    add_h1(story, "3. Sponsoring und Foerdermittel")
    add_para(story, "Sponsoring-Moeglichkeiten: Parteitagssponsoring (Standbuchung 2.000-10.000 Euro), "
             "Veranstaltungssponsoring (ab 500 Euro), Anzeigen in Parteipublikationen. "
             "Foerdermittel: Politische Stiftungen (fuer Bildungsarbeit), EU-Foerderprogramme "
             "(fuer grenzueberschreitende Projekte), kommunale Foerdermittel (fuer Jugendarbeit). "
             "Jede Sponsoring-Vereinbarung muss vom Schatzmeister genehmigt werden.")

    add_h1(story, "4. Crowdfunding")
    add_para(story, "Fuer einzelne Kampagnen und Projekte setzen wir zunehmend auf Crowdfunding. "
             "Plattform: Eigene Crowdfunding-Seite auf der Partei-Website (keine externen Plattformen, "
             "um Datenschutz und Rechenschaftspflicht zu gewaehrleisten). Erfolgsbeispiele: "
             "Klimakampagne 2025 (127.000 Euro von 3.400 Spendern in 6 Wochen), "
             "Jugendkampagne 'Zukunft jetzt' (45.000 Euro von 1.200 Spendern). "
             "Erfolgsfaktoren: Konkretes Ziel, emotionale Geschichte, regelmaessige Updates, "
             "Dank an Spender, Social-Media-Begleitung. Mindestlaufzeit: 4 Wochen, max. 8 Wochen.")

    add_h1(story, "5. Steuerliche Aspekte")
    add_para(story, "Spenden an Parteien sind steuerlich beguenstigt: 50% der Zuwendungen, maximal "
             "825 Euro fuer Einzelpersonen (1.650 Euro fuer Verheiratete) werden direkt von der "
             "Steuerschuld abgezogen. Darueber hinaus koennen bis zu 1.650 Euro (3.300 Euro "
             "fuer Verheiratete) als Sonderausgaben geltend gemacht werden. "
             "Spendenbescheinigungen werden automatisch im Januar des Folgejahres versandt.")


def schulung_campaigning(story):
    add_para(story, "Schulungsunterlagen Campaigning | Wahlkampfleitung | Dozent: Markus Brenner")

    add_h1(story, "1. Grundlagen der Kampagnenplanung")
    add_para(story, "Eine erfolgreiche politische Kampagne verbindet klare Botschaften mit zielgerichteter "
             "Ansprache. Die Planungsphase beginnt mindestens 12 Monate vor dem Wahltag. "
             "Kernelemente: Zielsetzung (Stimmenanteil, Direktmandate), Zielgruppen-Analyse, "
             "Botschaftsentwicklung, Kanalstrategie, Budget, Personal, Zeitplan. "
             "Die Kampagnenleitung liegt beim Wahlkampfleiter, der dem Vorstand berichtet.")

    add_h1(story, "2. Mobilisierung der Basis")
    add_para(story, "Die Mobilisierung unserer 78.500 Mitglieder ist entscheidend fuer den Wahlerfolg. "
             "Instrumente: Mobilisierungs-App 'DZP Aktiv' mit Push-Benachrichtigungen, "
             "regionale Aktionsteams in jedem Kreisverband (Ziel: 50 aktive Wahlkaempfer pro Kreis), "
             "Telefonbanking mit geschulten Ehrenamtlichen, persoenliche Ansprache durch "
             "Mandatstraeger und Funktionstraeger. Ziel: 30% der Mitglieder aktiv im Wahlkampf.")

    add_page_break(story)
    add_h1(story, "3. Haustuerwahlkampf")
    add_para(story, "Der Haustuerwahlkampf ist nachweislich die effektivste Form der Waehleransprache. "
             "Studien zeigen eine Steigerung der Wahlbeteiligung um 5-8 Prozentpunkte in bearbeiteten "
             "Gebieten. Vorgehen: 2er-Teams, Einsatzzeit 17:00-20:00 Uhr (beste Erreichbarkeit), "
             "standardisierter Gespraechsleitfaden mit 3 Kernbotschaften, Materialpaket "
             "(Flyer, Give-away, Rueckmeldepostkarte). Ziel: 500.000 Haustuergespraeche bundesweit. "
             "Schulung: Jeder Haustuerwahlkaempfer absolviert ein 3-stuendiges Training.")

    add_h1(story, "4. Informationsstaende und Kundgebungen")
    add_para(story, "Informationsstaende: Standort in Fussgaengerzonen, vor Supermaerkten (Genehmigung "
             "einholen!), bei lokalen Events. Ausstattung: Pavillon im Corporate Design, "
             "Aufsteller mit Kernbotschaften, Flyer und Broschueren, Give-aways (Kugelschreiber, "
             "Stoffbeutel, Gummibaerchen), Unterschriftenlisten. Kundgebungen: Rechtzeitig anmelden "
             "(mindestens 48 Stunden vorher bei der Versammlungsbehoerde), Buehne und Technik buchen, "
             "Ordnerdienst organisieren, Sanitaeter bei mehr als 500 erwarteten Teilnehmern.")

    add_h1(story, "5. Kampagnen-Evaluation")
    add_para(story, "Nach jeder Kampagne wird eine systematische Evaluation durchgefuehrt: "
             "Wurden die Ziele erreicht? Welche Kanaele waren am effektivsten? Wie war die "
             "Medienresonanz? Was hat das Feedback der Waehler ergeben? Budget-Ist vs. Budget-Soll. "
             "Die Ergebnisse fliessen in die naechste Kampagnenplanung ein. "
             "Der Evaluationsbericht wird innerhalb von 4 Wochen nach Wahlabend erstellt.")


def schulung_datenschutz_intern(story):
    add_para(story, "DSGVO-Schulung fuer Ehrenamtliche | Datenschutzbeauftragter Dr. Frank Meister | 2026")

    add_h1(story, "1. Warum Datenschutz jeden betrifft")
    add_para(story, "Als Ehrenamtliche in der DZP kommen Sie regelmaessig mit personenbezogenen Daten "
             "in Beruehrung: Mitgliederlisten, Kontaktdaten, Fotos von Veranstaltungen, "
             "Unterschriftensammlungen. Die DSGVO gilt fuer alle, die personenbezogene Daten "
             "verarbeiten - auch fuer Ehrenamtliche. Verstoesse koennen zu Bussgeldern von bis zu "
             "20 Mio. Euro fuehren. Dieses Schulungsmaterial gibt Ihnen die wichtigsten Regeln an die Hand.")

    add_h1(story, "2. Grundprinzipien der DSGVO")
    add_bullet(story, "Rechtmaessigkeit: Datenverarbeitung nur mit Rechtsgrundlage (Einwilligung, Vertrag, berechtigtes Interesse)")
    add_bullet(story, "Zweckbindung: Daten nur fuer den angegebenen Zweck verwenden")
    add_bullet(story, "Datenminimierung: Nur so viele Daten erheben wie noetig")
    add_bullet(story, "Richtigkeit: Daten muessen aktuell und korrekt sein")
    add_bullet(story, "Speicherbegrenzung: Daten loeschen, wenn nicht mehr benoetigt")
    add_bullet(story, "Vertraulichkeit: Schutz vor unbefugtem Zugriff")

    add_page_break(story)
    add_h1(story, "3. Praktische Checkliste fuer Ehrenamtliche")
    add_bullet(story, "Mitgliederlisten nie per unverschluesselter E-Mail versenden (nur ueber das Portal)")
    add_bullet(story, "Keine Mitgliederdaten auf privaten USB-Sticks speichern")
    add_bullet(story, "Ausdrucke mit personenbezogenen Daten schreddern, nicht in den Papierkorb")
    add_bullet(story, "Bei Infostaenden: Unterschriftenlisten nach Aktion sofort an die Geschaeftsstelle")
    add_bullet(story, "Fotos: Einwilligung einholen, besonders bei Kindern")
    add_bullet(story, "WhatsApp-Gruppen: Keine Mitgliederdaten in Gruppen teilen, Signal bevorzugen")
    add_bullet(story, "Laptop/Handy mit Passwort/PIN schuetzen, automatische Bildschirmsperre aktivieren")
    add_bullet(story, "Bei Datenpanne (z.B. verlorener USB-Stick): Sofort melden an datenschutz@dzp-partei.de")

    add_h1(story, "4. Besondere Situationen im Wahlkampf")
    add_para(story, "Haustuerwahlkampf: Die gesammelten Daten (Name, Adresse, Anliegen) duerfen nur "
             "fuer den Wahlkampf verwendet werden und sind nach der Wahl zu loeschen. "
             "Waehleransprache per Telefon: Nur mit vorheriger Einwilligung zulaessig. "
             "Social Media: Keine Screenshots von privaten Profilen verwenden. "
             "Waehlerdatenbanken: Zugang nur fuer autorisierte Personen, Logbuch fuehren.")

    add_h1(story, "5. Ihre Rechte und Ansprechpartner")
    add_para(story, "Datenschutzbeauftragter: Dr. Frank Meister, datenschutz@dzp-partei.de, "
             "Tel. 030-1234567-50. Sprechzeiten: Di und Do 10:00-12:00 Uhr. "
             "Datenschutz-Hotline fuer Ehrenamtliche: 030-1234567-55 (Mo-Fr 9:00-17:00). "
             "Online-Schulung: lernen.dzp-partei.de/datenschutz (Pflichtschulung, jaehrlich zu wiederholen). "
             "Bei Fragen oder Unsicherheiten: Lieber einmal zu viel fragen als einen Fehler machen!")


# ==============================================================================
# MAIN
# ==============================================================================

DOCUMENTS = [
    # Kategorie 1: Politik-Strategie
    ("wahlkampf_strategie_2026.pdf", "Digitale Wahlkampfstrategie 2026", wahlkampf_strategie_2026),
    ("positionspapier_klimapolitik.pdf", "Positionspapier Klimapolitik", positionspapier_klimapolitik),
    ("positionspapier_sozialpolitik.pdf", "Positionspapier Sozialpolitik", positionspapier_sozialpolitik),
    ("interne_satzung.pdf", "Satzung der Demokratischen Zukunftspartei e.V.", interne_satzung),
    ("gremienstruktur.pdf", "Gremienstruktur der DZP", gremienstruktur),
    ("mitgliederordnung.pdf", "Mitgliederordnung", mitgliederordnung),
    ("koalitionsvertrag_entwurf.pdf", "Koalitionsvertrag - Verhandlungsentwurf", koalitionsvertrag_entwurf),
    # Kategorie 2: Interne Prozesse
    ("prozess_antrag_stellen.pdf", "Prozess: Antraege stellen und behandeln", prozess_antrag_stellen),
    ("prozess_veranstaltung_organisieren.pdf", "Prozess: Veranstaltungen organisieren", prozess_veranstaltung_organisieren),
    ("prozess_pressemitteilung.pdf", "Prozess: Pressemitteilungen erstellen und freigeben", prozess_pressemitteilung),
    ("prozess_reisekostenabrechnung.pdf", "Prozess: Reisekostenabrechnung", prozess_reisekostenabrechnung),
    ("prozess_mitgliederverwaltung.pdf", "Prozess: Mitgliederverwaltung", prozess_mitgliederverwaltung),
    ("prozess_beschlussverfolgung.pdf", "Prozess: Beschlussverfolgung", prozess_beschlussverfolgung),
    ("leitfaden_ehrenamtliche.pdf", "Leitfaden fuer Ehrenamtliche", leitfaden_ehrenamtliche),
    # Kategorie 3: Externe Kommunikation
    ("leitfaden_social_media.pdf", "Leitfaden Social Media", leitfaden_social_media),
    ("krisenhandbuch_shitstorm.pdf", "Krisenhandbuch: Umgang mit Shitstorms", krisenhandbuch_shitstorm),
    ("presseverteiler.pdf", "Presseverteiler", presseverteiler),
    ("corporate_design_manual.pdf", "Corporate Design Manual", corporate_design_manual),
    ("leitfaden_offentlichkeitsarbeit.pdf", "Leitfaden Oeffentlichkeitsarbeit", leitfaden_offentlichkeitsarbeit),
    ("datenschutz_kommunikation.pdf", "Datenschutz in der Kommunikation", datenschutz_kommunikation),
    # Kategorie 4: Schulungsmaterial
    ("schulung_rhetorik_basics.pdf", "Schulung: Rhetorik-Grundlagen", schulung_rhetorik_basics),
    ("schulung_moderation_gremien.pdf", "Schulung: Moderation in Gremien", schulung_moderation_gremien),
    ("schulung_konfliktmanagement.pdf", "Schulung: Konfliktmanagement", schulung_konfliktmanagement),
    ("onboarding_neue_mitglieder.pdf", "Onboarding: Willkommen bei der DZP", onboarding_neue_mitglieder),
    ("schulung_fundraising.pdf", "Schulung: Fundraising und Spendenakquise", schulung_fundraising),
    ("schulung_campaigning.pdf", "Schulung: Campaigning und Wahlkampf", schulung_campaigning),
    ("schulung_datenschutz_intern.pdf", "Schulung: Datenschutz fuer Ehrenamtliche", schulung_datenschutz_intern),
]

if __name__ == "__main__":
    print(f"Generating {len(DOCUMENTS)} PDFs into {OUTPUT_DIR}...")
    for filename, title, func in DOCUMENTS:
        build_pdf(filename, title, func)
    print(f"\nDone! {len(DOCUMENTS)} PDFs generated in {OUTPUT_DIR}")
