/**
 * JsonUtils.gs - Parsing JSON robuste
 *
 * Port de domain/json_utils.py
 */
var JsonUtils = (function() {
  /**
   * Parse du JSON de maniere ultra robuste.
   *
   * Strategie :
   * 1) tentative directe JSON.parse
   * 2) extraction d'un bloc entre ```json ... ``` ou ``` ... ```
   * 3) fallback : premier '{' au dernier '}'
   * 4) sinon : null
   */
  function safeJsonParse(text) {
    if (!text) return null;
    var raw = text.trim();
    // 1) Tentative directe
    try {
      return JSON.parse(raw);
    } catch (e) {
      // continue
    }
    // 2) Bloc markdown ```json ... ```
    var fenceMatch = raw.match(/```(?:json)?\s*(\{[\s\S]*?\})\s*```/i);
    if (fenceMatch) {
      try {
        return JSON.parse(fenceMatch[1].trim());
      } catch (e) {
        Logger.log('safeJsonParse: echec parse bloc markdown: ' + e.message);
      }
    }
    // 3) Fallback brutal : premier '{' au dernier '}'
    var start = raw.indexOf('{');
    var end = raw.lastIndexOf('}');
    if (start !== -1 && end !== -1 && end > start) {
      var candidate = raw.substring(start, end + 1);
      try {
        return JSON.parse(candidate);
      } catch (e) {
        Logger.log('safeJsonParse: echec parse fallback: ' + e.message);
      }
    }
    Logger.log('safeJsonParse: impossible de parser JSON. Contenu tronque: ' + raw.substring(0, 300));
    return null;
  }
  return {
    safeJsonParse: safeJsonParse
  };
})();