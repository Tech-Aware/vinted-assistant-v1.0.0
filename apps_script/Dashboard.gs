/**
 * Dashboard.gs - Dashboard interactif HTML pour la feuille "Générations".
 *
 * Approche "HtmlService" : la feuille Générations est lue côté Apps Script,
 * agrégée par cette couche, puis transmise en JSON à DashboardHtml.html qui rend
 * les graphiques avec Google Charts (chargé depuis gstatic.com).
 *
 * Structure des colonnes (LOG_HEADERS, voir Code.gs) :
 *   1  Date          (Date)
 *   2  Agent         (email)
 *   3  Profil        (jean_levis | pull | jacket_carhart)
 *   4  Type article  (Jean | Pull | Veste | ...)
 *   5  Marque
 *   6  Modele
 *   7  Premium       (boolean)
 *   8  Taille FR
 *   9  Taille US
 *   10 Rise          (Basse | Moyenne | Haute)
 *   11 Couleur
 *   12 Matiere
 *   13 Coupe
 *   14 Genre
 *   15 Prix
 *   16 Etat
 *   17 SKU
 *   18 Timestamp     (string yyyy-MM-dd HH:mm:ss)
 *   19 Duree (min)
 *   20 Coût ($)
 *   21 Défauts       (boolean checkbox)
 */

// ============================================================
// Entrée de menu : ouverture du dashboard
// ============================================================
function openDashboard() {
  var html = HtmlService.createHtmlOutputFromFile('DashboardHtml')
    .setWidth(1280)
    .setHeight(820)
    .setTitle('Vinted Assistant — Dashboard');
  SpreadsheetApp.getUi().showModalDialog(html, '📊 Vinted Assistant — Dashboard Générations');
}

// ============================================================
// Lecture + agrégation des données pour le dashboard
// ============================================================
/**
 * Lit la feuille "Générations" du Google Sheet configuré (LOG_SHEET_ID,
 * fallback sur le classeur actif) et renvoie un objet agrégé prêt à
 * être consommé par DashboardHtml.html / Google Charts.
 *
 * @returns {Object} Données agrégées (voir DashboardData_ ci-dessous) ou
 *                   { error: string } en cas d'échec.
 */
function getDashboardData() {
  try {
    var sheetId = Config.getLogSheetId();
    var spreadsheet = sheetId
      ? SpreadsheetApp.openById(sheetId)
      : SpreadsheetApp.getActiveSpreadsheet();
    var sheet = spreadsheet.getSheetByName('Générations');
    if (!sheet) {
      return { error: 'Feuille "Générations" introuvable dans le Google Sheet configuré.' };
    }
    var lastRow = sheet.getLastRow();
    if (lastRow < 2) {
      return DashboardData_.empty();
    }
    // 24 colonnes attendues (ajout de Motif/Origine/Etiquettes coupées entre
    // Genre et Prix), on lit ce qui existe pour rester tolérant aux feuilles
    // plus anciennes / futures.
    var lastCol = Math.max(sheet.getLastColumn(), 24);
    var values = sheet.getRange(2, 1, lastRow - 1, lastCol).getValues();
    return DashboardData_.build(values);
  } catch (err) {
    Logger.log('getDashboardData error: ' + err.message);
    return { error: 'Erreur lecture dashboard : ' + err.message };
  }
}

// ============================================================
// Construction des agrégats
// ============================================================
var DashboardData_ = (function () {

  // Index 0-based des colonnes (cf. LOG_HEADERS dans Code.gs)
  var COL = {
    DATE: 0, AGENT: 1, PROFIL: 2, TYPE: 3, MARQUE: 4, MODELE: 5,
    PREMIUM: 6, TAILLE_FR: 7, TAILLE_US: 8, RISE: 9, COULEUR: 10,
    MATIERE: 11, COUPE: 12, GENRE: 13,
    PATTERN: 14, ORIGIN: 15, LABELS_CUT: 16,
    PRIX: 17, ETAT: 18, SKU: 19,
    TIMESTAMP: 20, DUREE: 21, COUT: 22, DEFAUTS: 23
  };

  function empty() {
    return {
      generatedAt: new Date().toISOString(),
      totalRows: 0,
      overview: { total: 0, lastGeneration: null, avgDuration: null, last7DaysCount: 0 },
      byAgent: [], byProfil: [], byArticleType: [], byMarque: [], byModele: [],
      byModeleNamed: [],
      premium: { yes: 0, no: 0 },
      premiumBreakdown: { budget: 0, standard: 0, candidate: 0, confirmed: 0 },
      byTailleFr: [], byTailleUs: [], byRise: [], byCouleur: [], byMatiere: [],
      byCoupe: [], byGenre: [], byEtat: [],
      pricing: {
        avg: null, min: null, max: null, count: 0,
        distribution: [], avgByProfil: [], avgByEtat: [], avgByGenre: [],
        avgOverTime: []
      },
      defects: { withDefects: 0, withoutDefects: 0, avgPriceWith: null, avgPriceWithout: null },
      trends: { perDay: [], cumulativeCost: [], avgDurationPerDay: [], avgPricePerWeek: [],
                modelByWeek: [], topModels: [] },
      costs: { total: 0, avg: null, byAgent: [], durationCostScatter: [] }
    };
  }

  // -------- Helpers --------
  function s(v) {
    if (v == null) return '';
    if (typeof v === 'number' && isFinite(v)) return String(v);
    return String(v).trim();
  }
  function num(v) {
    if (v === '' || v == null) return null;
    if (typeof v === 'number') return isFinite(v) ? v : null;
    var n = parseFloat(String(v).replace(',', '.').replace(/[^0-9.\-]/g, ''));
    return isNaN(n) ? null : n;
  }
  function bool(v) {
    if (v === true) return true;
    if (v === false) return false;
    var t = s(v).toLowerCase();
    return t === 'true' || t === 'vrai' || t === '1' || t === 'oui' || t === 'yes';
  }
  function asDate(v) {
    if (v instanceof Date) return isNaN(v.getTime()) ? null : v;
    if (!v) return null;
    var d = new Date(v);
    return isNaN(d.getTime()) ? null : d;
  }
  function fmtDate(d) {
    if (!d) return '';
    return Utilities.formatDate(d, Session.getScriptTimeZone(), 'yyyy-MM-dd');
  }
  function fmtWeek(d) {
    if (!d) return '';
    return Utilities.formatDate(d, Session.getScriptTimeZone(), "yyyy-'W'ww");
  }
  function fmtDateTime(d) {
    if (!d) return '';
    return Utilities.formatDate(d, Session.getScriptTimeZone(), 'yyyy-MM-dd HH:mm');
  }
  function bumpCount(map, key) {
    if (!key) return;
    map[key] = (map[key] || 0) + 1;
  }
  function toCountArray(map, opts) {
    opts = opts || {};
    var arr = [];
    Object.keys(map).forEach(function (k) { arr.push({ key: k, count: map[k] }); });
    arr.sort(function (a, b) {
      var d = b.count - a.count;
      if (d !== 0) return d;
      return a.key < b.key ? -1 : (a.key > b.key ? 1 : 0);
    });
    if (opts.topN && arr.length > opts.topN) {
      var rest = arr.slice(opts.topN);
      var head = arr.slice(0, opts.topN);
      var others = rest.reduce(function (acc, x) { return acc + x.count; }, 0);
      if (others > 0) head.push({ key: 'Autres', count: others });
      return head;
    }
    return arr;
  }
  function avgFromMap(sumCountMap) {
    var arr = [];
    Object.keys(sumCountMap).forEach(function (k) {
      var sc = sumCountMap[k];
      if (sc.count > 0) arr.push({ key: k, avg: sc.sum / sc.count, count: sc.count });
    });
    arr.sort(function (a, b) { return b.avg - a.avg; });
    return arr;
  }
  function addToBucket(map, key, value) {
    if (!key) return;
    if (!map[key]) map[key] = { sum: 0, count: 0 };
    map[key].sum += value;
    map[key].count += 1;
  }

  // Histogramme des prix (largeur 5€, plafond 100€+).
  function priceDistribution(prices) {
    var buckets = {};
    var bucketWidth = 5;
    prices.forEach(function (p) {
      if (p == null) return;
      var label;
      if (p >= 100) label = '100+';
      else {
        var lo = Math.floor(p / bucketWidth) * bucketWidth;
        label = lo + '–' + (lo + bucketWidth);
      }
      buckets[label] = (buckets[label] || 0) + 1;
    });
    // Tri "naturel" pour avoir 0–5, 5–10, …, 95–100, 100+
    var keys = Object.keys(buckets).sort(function (a, b) {
      function low(x) { return x === '100+' ? 100 : parseInt(x.split('–')[0], 10); }
      return low(a) - low(b);
    });
    return keys.map(function (k) { return { key: k, count: buckets[k] }; });
  }

  // -------- Construction --------
  function build(values) {
    var out = empty();
    out.totalRows = values.length;

    // Maps d'agrégation
    var agentCount = {}, agentCost = {}, agentDuration = {};
    var profilMap = {}, typeMap = {}, marqueMap = {}, modeleMap = {}, modeleNamedMap = {};
    var tailleFrMap = {}, tailleUsMap = {}, riseMap = {};
    var couleurMap = {}, matiereMap = {}, coupeMap = {}, genreMap = {}, etatMap = {};

    var prices = [];
    var pricesByProfil = {}, pricesByEtat = {}, pricesByGenre = {};
    var pricesByDate = {}, pricesByWeek = {};
    var countByDate = {}, durationByDate = {}, costByDate = {};
    var scatter = [];

    var premiumYes = 0, premiumNo = 0;
    var premiumBreakdown = { budget: 0, standard: 0, candidate: 0, confirmed: 0 };
    var modelByWeek = {}; // { weekKey: { modelKey: count } }
    var totalCost = 0, costCount = 0;
    var defectsTrue = 0, defectsFalse = 0;
    var sumPriceDefects = 0, cntPriceDefects = 0;
    var sumPriceNoDefects = 0, cntPriceNoDefects = 0;

    var lastDate = null;
    var totalDurationSum = 0, totalDurationCount = 0;

    var now = new Date();
    var sevenDaysAgo = new Date(now.getTime() - 7 * 24 * 3600 * 1000);
    var last7Days = 0;

    for (var i = 0; i < values.length; i++) {
      var r = values[i];
      var date = asDate(r[COL.DATE]);
      if (date) {
        if (!lastDate || date.getTime() > lastDate.getTime()) lastDate = date;
        if (date.getTime() >= sevenDaysAgo.getTime()) last7Days++;
        var dKey = fmtDate(date);
        var wKey = fmtWeek(date);
        countByDate[dKey] = (countByDate[dKey] || 0) + 1;
        if (!pricesByDate[dKey]) pricesByDate[dKey] = { sum: 0, count: 0 };
        if (!pricesByWeek[wKey]) pricesByWeek[wKey] = { sum: 0, count: 0 };
      }

      var agent = s(r[COL.AGENT]);
      if (agent) {
        agentCount[agent] = (agentCount[agent] || 0) + 1;
        if (!agentCost[agent]) agentCost[agent] = { sum: 0, count: 0 };
        if (!agentDuration[agent]) agentDuration[agent] = { sum: 0, count: 0 };
      }

      bumpCount(profilMap, s(r[COL.PROFIL]));
      bumpCount(typeMap, s(r[COL.TYPE]));
      bumpCount(marqueMap, s(r[COL.MARQUE]));
      var profil = s(r[COL.PROFIL]).toLowerCase();
      var modeleRaw = r[COL.MODELE];
      // On agrège les modèles uniquement pour le profil jean_levis,
      // en utilisant normalizeLevisModel_() pour séparer numériques, nommés et Autres.
      if (profil === 'jean_levis') {
        var normModel = normalizeLevisModel_(modeleRaw);
        bumpCount(modeleMap, normModel);
        // Modèles nommés seuls (pas les codes 3 chiffres ni "Autres")
        if (normModel !== 'Autres' && !/^\d{3}$/.test(normModel)) {
          bumpCount(modeleNamedMap, normModel);
        }
        // Répartition premium en 4 catégories
        var brand_ = s(r[COL.MARQUE]);
        var isPrem_ = bool(r[COL.PREMIUM]);
        var seg_ = categorizePremiumSegment_(brand_, normModel, isPrem_);
        premiumBreakdown[seg_]++;
        // Tendance modèles par semaine
        if (date) {
          var wKeyM = fmtWeek(date);
          if (!modelByWeek[wKeyM]) modelByWeek[wKeyM] = {};
          modelByWeek[wKeyM][normModel] = (modelByWeek[wKeyM][normModel] || 0) + 1;
        }
      }

      if (bool(r[COL.PREMIUM])) premiumYes++; else premiumNo++;

      bumpCount(tailleFrMap, s(r[COL.TAILLE_FR]));
      bumpCount(tailleUsMap, s(r[COL.TAILLE_US]));
      bumpCount(riseMap, s(r[COL.RISE]));

      // Couleur / Matière peuvent contenir plusieurs valeurs séparées par ", "
      s(r[COL.COULEUR]).split(/\s*,\s*/).forEach(function (c) {
        if (c) bumpCount(couleurMap, c);
      });
      s(r[COL.MATIERE]).split(/\s*,\s*/).forEach(function (m) {
        if (m) bumpCount(matiereMap, m);
      });
      bumpCount(coupeMap, s(r[COL.COUPE]));
      bumpCount(genreMap, s(r[COL.GENRE]).toLowerCase());
      bumpCount(etatMap, s(r[COL.ETAT]).toLowerCase());

      var price = num(r[COL.PRIX]);
      if (price != null) {
        prices.push(price);
        addToBucket(pricesByProfil, s(r[COL.PROFIL]), price);
        addToBucket(pricesByEtat, s(r[COL.ETAT]).toLowerCase(), price);
        addToBucket(pricesByGenre, s(r[COL.GENRE]).toLowerCase(), price);
        if (date) {
          pricesByDate[fmtDate(date)].sum += price;
          pricesByDate[fmtDate(date)].count += 1;
          pricesByWeek[fmtWeek(date)].sum += price;
          pricesByWeek[fmtWeek(date)].count += 1;
        }
      }

      var duree = num(r[COL.DUREE]);
      if (duree != null) {
        totalDurationSum += duree;
        totalDurationCount += 1;
        if (agent) {
          agentDuration[agent].sum += duree;
          agentDuration[agent].count += 1;
        }
        if (date) {
          if (!durationByDate[fmtDate(date)]) durationByDate[fmtDate(date)] = { sum: 0, count: 0 };
          durationByDate[fmtDate(date)].sum += duree;
          durationByDate[fmtDate(date)].count += 1;
        }
      }

      var cout = num(r[COL.COUT]);
      if (cout != null) {
        totalCost += cout;
        costCount += 1;
        if (agent) {
          agentCost[agent].sum += cout;
          agentCost[agent].count += 1;
        }
        if (date) {
          costByDate[fmtDate(date)] = (costByDate[fmtDate(date)] || 0) + cout;
        }
        if (duree != null) {
          scatter.push({ duration: duree, cost: cout });
        }
      }

      var hasDefect = bool(r[COL.DEFAUTS]);
      if (hasDefect) {
        defectsTrue++;
        if (price != null) { sumPriceDefects += price; cntPriceDefects++; }
      } else {
        defectsFalse++;
        if (price != null) { sumPriceNoDefects += price; cntPriceNoDefects++; }
      }
    }

    // ---- Vue d'ensemble ----
    out.overview.total = values.length;
    out.overview.lastGeneration = lastDate ? fmtDateTime(lastDate) : null;
    out.overview.avgDuration = totalDurationCount > 0
      ? Math.round((totalDurationSum / totalDurationCount) * 100) / 100
      : null;
    out.overview.last7DaysCount = last7Days;

    // ---- Agents ----
    out.byAgent = Object.keys(agentCount).map(function (a) {
      var sc = agentCost[a] || { sum: 0, count: 0 };
      var sd = agentDuration[a] || { sum: 0, count: 0 };
      return {
        agent: a,
        count: agentCount[a],
        totalCost: Math.round(sc.sum * 1000000) / 1000000,
        avgCost: sc.count > 0 ? Math.round((sc.sum / sc.count) * 1000000) / 1000000 : null,
        avgDuration: sd.count > 0 ? Math.round((sd.sum / sd.count) * 100) / 100 : null
      };
    }).sort(function (a, b) { return b.count - a.count; });

    // ---- Catalogue produit ----
    out.byProfil       = toCountArray(profilMap);
    out.byArticleType  = toCountArray(typeMap);
    out.byMarque       = toCountArray(marqueMap, { topN: 10 });
    out.byModele       = toCountArray(modeleMap);
    out.byModeleNamed  = toCountArray(modeleNamedMap);
    out.premium        = { yes: premiumYes, no: premiumNo };
    out.premiumBreakdown = premiumBreakdown;

    // ---- Dimensions ----
    out.byTailleFr = toCountArray(tailleFrMap);
    out.byTailleUs = toCountArray(tailleUsMap);
    out.byRise     = toCountArray(riseMap);
    out.byCouleur  = toCountArray(couleurMap, { topN: 10 });
    out.byMatiere  = toCountArray(matiereMap, { topN: 10 });
    out.byCoupe    = toCountArray(coupeMap);
    out.byGenre    = toCountArray(genreMap);
    out.byEtat     = toCountArray(etatMap);

    // ---- Pricing ----
    if (prices.length > 0) {
      var sum = prices.reduce(function (a, b) { return a + b; }, 0);
      out.pricing.avg = Math.round((sum / prices.length) * 100) / 100;
      out.pricing.min = Math.min.apply(null, prices);
      out.pricing.max = Math.max.apply(null, prices);
      out.pricing.count = prices.length;
      out.pricing.distribution = priceDistribution(prices);
      out.pricing.avgByProfil = avgFromMap(pricesByProfil).map(roundAvg);
      out.pricing.avgByEtat   = avgFromMap(pricesByEtat).map(roundAvg);
      out.pricing.avgByGenre  = avgFromMap(pricesByGenre).map(roundAvg);
      // Évolution prix moyen par jour (chronologique)
      var dateKeys = Object.keys(pricesByDate).sort();
      out.pricing.avgOverTime = dateKeys
        .filter(function (k) { return pricesByDate[k].count > 0; })
        .map(function (k) {
          return {
            date: k,
            avg: Math.round((pricesByDate[k].sum / pricesByDate[k].count) * 100) / 100,
            count: pricesByDate[k].count
          };
        });
    }

    // ---- Défauts ----
    out.defects.withDefects    = defectsTrue;
    out.defects.withoutDefects = defectsFalse;
    out.defects.avgPriceWith    = cntPriceDefects   > 0 ? Math.round((sumPriceDefects   / cntPriceDefects)   * 100) / 100 : null;
    out.defects.avgPriceWithout = cntPriceNoDefects > 0 ? Math.round((sumPriceNoDefects / cntPriceNoDefects) * 100) / 100 : null;

    // ---- Tendances ----
    var sortedDays = Object.keys(countByDate).sort();
    out.trends.perDay = sortedDays.map(function (k) { return { date: k, count: countByDate[k] }; });
    out.trends.avgDurationPerDay = sortedDays
      .filter(function (k) { return durationByDate[k] && durationByDate[k].count > 0; })
      .map(function (k) {
        return { date: k, avg: Math.round((durationByDate[k].sum / durationByDate[k].count) * 100) / 100 };
      });
    var cumul = 0;
    out.trends.cumulativeCost = sortedDays.map(function (k) {
      cumul += (costByDate[k] || 0);
      return { date: k, total: Math.round(cumul * 1000000) / 1000000 };
    });
    var weekKeys = Object.keys(pricesByWeek).sort();
    out.trends.avgPricePerWeek = weekKeys
      .filter(function (k) { return pricesByWeek[k].count > 0; })
      .map(function (k) {
        return { week: k, avg: Math.round((pricesByWeek[k].sum / pricesByWeek[k].count) * 100) / 100 };
      });

    // Tendance modèles (top 3) par semaine — "Autres" exclu car trop générique
    var top3Models = toCountArray(modeleMap)
      .filter(function (x) { return x.key !== 'Autres'; })
      .slice(0, 3)
      .map(function (x) { return x.key; });
    var weekModelKeys = Object.keys(modelByWeek).sort();
    out.trends.topModels = top3Models;
    out.trends.modelByWeek = weekModelKeys.map(function (wk) {
      var row = { week: wk };
      top3Models.forEach(function (m) { row[m] = (modelByWeek[wk][m] || 0); });
      return row;
    });

    // ---- Coûts IA ----
    out.costs.total = Math.round(totalCost * 1000000) / 1000000;
    out.costs.avg = costCount > 0 ? Math.round((totalCost / costCount) * 1000000) / 1000000 : null;
    out.costs.byAgent = out.byAgent.map(function (a) {
      return { agent: a.agent, totalCost: a.totalCost, avgCost: a.avgCost };
    });
    out.costs.durationCostScatter = scatter;

    out.generatedAt = new Date().toISOString();
    return out;
  }

  function roundAvg(x) {
    return { key: x.key, avg: Math.round(x.avg * 100) / 100, count: x.count };
  }

  return { build: build, empty: empty };
})();
