(function () {
  "use strict";

  var MAX_ENCODED = 22369622;
  var MAX_DECODED = 16777216;
  var MAX_NODES = 250000;
  var MAX_STRINGS = 100000;
  var MAX_STRING_BYTES = 8388608;
  var MAX_DEPTH = 32;
  var MAX_ACCEPTED_STATES = 65536;
  var MAX_VIEW_ITEMS = 768;
  var MAX_TARGETS = 4096;
  var MAX_STEPS = 5120;
  var MAX_DECK_WAIT_MS = 600000;
  var DEFAULT_PAGE_PAUSE_MS = 800;
  var SPECIAL = new Set(["__proto__", "prototype", "constructor"]);
  var RESERVED_OUTPUTS = new Set(["score", "classification", "decisionStatus", "recommendation"]);
  var SAFE_ID = /^[a-z][a-z0-9_-]{0,63}$/;
  var CANONICAL_DECIMAL = /^-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?$/;
  var RAW_DECIMAL = /^[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)$/;

  function invariant(condition, code) {
    if (!condition) {
      var failure = new Error(code);
      failure.code = code;
      throw failure;
    }
  }

  function own(value, key) {
    return Object.prototype.hasOwnProperty.call(value, key);
  }

  function plain(value) {
    return value !== null && typeof value === "object" && !Array.isArray(value);
  }

  function exactKeys(value, required, optional, code) {
    invariant(plain(value), code);
    var allowed = new Set(required.concat(optional || []));
    var keys = Object.keys(value);
    for (var index = 0; index < required.length; index += 1) {
      invariant(own(value, required[index]), code);
    }
    for (var keyIndex = 0; keyIndex < keys.length; keyIndex += 1) {
      invariant(allowed.has(keys[keyIndex]) && !SPECIAL.has(keys[keyIndex]), code);
    }
    return value;
  }

  function safeId(value, code) {
    invariant(typeof value === "string" && SAFE_ID.test(value) && !SPECIAL.has(value), code);
    return value;
  }

  function outputId(value, code) {
    invariant(typeof value === "string" && (SAFE_ID.test(value) || RESERVED_OUTPUTS.has(value)) && !SPECIAL.has(value), code);
    return value;
  }

  function scalarLength(value, code) {
    invariant(typeof value === "string", code);
    var count = 0;
    for (var index = 0; index < value.length; index += 1) {
      var unit = value.charCodeAt(index);
      if (unit >= 55296 && unit <= 56319) {
        invariant(index + 1 < value.length && value.charCodeAt(index + 1) >= 56320 && value.charCodeAt(index + 1) <= 57343, code);
        index += 1;
      } else {
        invariant(unit < 56320 || unit > 57343, code);
      }
      count += 1;
    }
    return count;
  }

  function text(value, code, maximum) {
    invariant(scalarLength(value, code) <= maximum, code);
    return value;
  }

  function utf8Length(value) {
    var count = 0;
    for (var index = 0; index < value.length; index += 1) {
      var unit = value.charCodeAt(index);
      if (unit < 128) {
        count += 1;
      } else if (unit < 2048) {
        count += 2;
      } else if (unit >= 55296 && unit <= 56319) {
        invariant(index + 1 < value.length, "E_DATA_UNICODE");
        var next = value.charCodeAt(index + 1);
        invariant(next >= 56320 && next <= 57343, "E_DATA_UNICODE");
        count += 4;
        index += 1;
      } else {
        invariant(unit < 56320 || unit > 57343, "E_DATA_UNICODE");
        count += 3;
      }
    }
    return count;
  }

  function preflightJson(source) {
    var cursor = 0;
    var nodes = 0;
    var strings = 0;
    var stringBytes = 0;

    function limits(depth) {
      invariant(depth <= MAX_DEPTH, "E_DATA_DEPTH");
      nodes += 1;
      invariant(nodes <= MAX_NODES, "E_DATA_NODES");
    }

    function space() {
      while (cursor < source.length && " \n\r\t".indexOf(source.charAt(cursor)) >= 0) {
        cursor += 1;
      }
    }

    function parseString() {
      invariant(source.charAt(cursor) === '"', "E_DATA_JSON");
      var start = cursor;
      cursor += 1;
      while (cursor < source.length) {
        var character = source.charAt(cursor);
        if (character === '"') {
          cursor += 1;
          var decoded = JSON.parse(source.slice(start, cursor));
          strings += 1;
          stringBytes += utf8Length(decoded);
          invariant(strings <= MAX_STRINGS && stringBytes <= MAX_STRING_BYTES, "E_DATA_STRINGS");
          return decoded;
        }
        if (character === "\\") {
          cursor += 1;
          invariant(cursor < source.length, "E_DATA_JSON");
          var escape = source.charAt(cursor);
          if (escape === "u") {
            invariant(/^[0-9A-Fa-f]{4}$/.test(source.slice(cursor + 1, cursor + 5)), "E_DATA_JSON");
            cursor += 4;
          } else {
            invariant('"\\/bfnrt'.indexOf(escape) >= 0, "E_DATA_JSON");
          }
        } else {
          invariant(character.charCodeAt(0) >= 32, "E_DATA_JSON");
        }
        cursor += 1;
      }
      invariant(false, "E_DATA_JSON");
    }

    function value(depth) {
      space();
      limits(depth);
      var token = source.charAt(cursor);
      if (token === "{") {
        cursor += 1;
        space();
        var names = new Set();
        if (source.charAt(cursor) !== "}") {
          while (true) {
            var name = parseString();
            invariant(!names.has(name) && !SPECIAL.has(name), "E_DATA_DUPLICATE");
            names.add(name);
            nodes += 1;
            invariant(nodes <= MAX_NODES, "E_DATA_NODES");
            space();
            invariant(source.charAt(cursor) === ":", "E_DATA_JSON");
            cursor += 1;
            value(depth + 1);
            space();
            if (source.charAt(cursor) === "}") {
              break;
            }
            invariant(source.charAt(cursor) === ",", "E_DATA_JSON");
            cursor += 1;
            space();
          }
        }
        cursor += 1;
        return;
      }
      if (token === "[") {
        cursor += 1;
        space();
        if (source.charAt(cursor) !== "]") {
          while (true) {
            value(depth + 1);
            space();
            if (source.charAt(cursor) === "]") {
              break;
            }
            invariant(source.charAt(cursor) === ",", "E_DATA_JSON");
            cursor += 1;
          }
        }
        cursor += 1;
        return;
      }
      if (token === '"') {
        parseString();
        return;
      }
      var remainder = source.slice(cursor);
      var number = remainder.match(/^-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?/);
      if (number) {
        cursor += number[0].length;
        return;
      }
      var literals = ["true", "false", "null"];
      for (var literalIndex = 0; literalIndex < literals.length; literalIndex += 1) {
        if (source.slice(cursor, cursor + literals[literalIndex].length) === literals[literalIndex]) {
          cursor += literals[literalIndex].length;
          return;
        }
      }
      invariant(false, "E_DATA_JSON");
    }

    space();
    value(0);
    space();
    invariant(cursor === source.length, "E_DATA_JSON");
  }

  function deepFreeze(value) {
    if (value && typeof value === "object" && !Object.isFrozen(value)) {
      var keys = Object.keys(value);
      for (var index = 0; index < keys.length; index += 1) {
        deepFreeze(value[keys[index]]);
      }
      Object.freeze(value);
    }
    return value;
  }

  var DECIMAL = (function () {
    function power(exponent) {
      var result = BigInt(1);
      for (var index = 0; index < exponent; index += 1) {
        result *= BigInt(10);
      }
      return result;
    }

    function roundDiv(numerator, denominator) {
      invariant(denominator !== BigInt(0), "E_DECIMAL_DIVIDE");
      var sign = BigInt(1);
      if (numerator < BigInt(0)) {
        sign = -sign;
        numerator = -numerator;
      }
      if (denominator < BigInt(0)) {
        sign = -sign;
        denominator = -denominator;
      }
      var quotient = numerator / denominator;
      var remainder = numerator % denominator;
      if (remainder * BigInt(2) >= denominator) {
        quotient += BigInt(1);
      }
      return sign * quotient;
    }

    function parse(value, scale) {
      invariant(typeof value === "string" && value.length <= 128 && value !== "-0" && CANONICAL_DECIMAL.test(value), "E_DECIMAL_CANONICAL");
      var negative = value.charAt(0) === "-";
      var unsigned = negative ? value.slice(1) : value;
      var pieces = unsigned.split(".");
      var fraction = pieces.length === 2 ? pieces[1] : "";
      invariant(fraction.length <= scale, "E_DECIMAL_SCALE");
      var units = BigInt(pieces[0] + fraction + "0".repeat(scale - fraction.length));
      if (negative) {
        units = -units;
      }
      invariant(units <= power(12 + scale) && units >= -power(12 + scale), "E_DECIMAL_BOUND");
      return units;
    }

    function scaleOf(value) {
      invariant(typeof value === "string" && value.length <= 128 && value !== "-0" && CANONICAL_DECIMAL.test(value), "E_DECIMAL_CANONICAL");
      var marker = value.indexOf(".");
      var scale = marker < 0 ? 0 : value.length - marker - 1;
      invariant(scale <= 6, "E_DECIMAL_SCALE");
      parse(value, scale);
      return scale;
    }

    function rescale(value, fromScale, toScale) {
      invariant(Number.isInteger(fromScale) && Number.isInteger(toScale) && fromScale >= 0 && toScale >= fromScale && toScale <= 6, "E_DECIMAL_SCALE");
      return value * power(toScale - fromScale);
    }

    function canonical(units, scale) {
      if (units === BigInt(0)) {
        return "0";
      }
      var negative = units < BigInt(0);
      var digits = String(negative ? -units : units);
      if (scale > 0) {
        digits = digits.padStart(scale + 1, "0");
        var whole = digits.slice(0, digits.length - scale);
        var fraction = digits.slice(digits.length - scale).replace(/0+$/, "");
        digits = fraction ? whole + "." + fraction : whole;
      }
      return (negative ? "-" : "") + digits;
    }

    function rawRational(value) {
      invariant(typeof value === "string" && value.length > 0 && value.length <= 128 && RAW_DECIMAL.test(value), "E_FRAGMENT_NUMBER");
      var negative = value.charAt(0) === "-";
      var unsigned = value.charAt(0) === "+" || negative ? value.slice(1) : value;
      var pieces = unsigned.split(".");
      var whole = pieces[0] || "0";
      var fraction = pieces.length === 2 ? pieces[1] : "";
      var digits = (whole + fraction).replace(/^0+(?=[0-9])/, "");
      var numerator = BigInt(digits || "0");
      return { numerator: negative ? -numerator : numerator, denominator: power(fraction.length) };
    }

    function snap(raw, control, scale) {
      var rational = rawRational(raw);
      var minimum = parse(control.min, scale);
      var maximum = parse(control.max, scale);
      var step = parse(control.step, scale);
      var scaledNumerator = rational.numerator * power(scale);
      var scaledMinimum = minimum * rational.denominator;
      var scaledMaximum = maximum * rational.denominator;
      if (scaledNumerator <= scaledMinimum) {
        return minimum;
      }
      if (scaledNumerator >= scaledMaximum) {
        return maximum;
      }
      var steps = roundDiv(scaledNumerator - scaledMinimum, step * rational.denominator);
      var accepted = minimum + steps * step;
      return accepted < minimum ? minimum : accepted > maximum ? maximum : accepted;
    }

    function positions(control, scale) {
      var minimum = parse(control.min, scale);
      var maximum = parse(control.max, scale);
      var step = parse(control.step, scale);
      invariant(minimum < maximum && step > BigInt(0) && (maximum - minimum) % step === BigInt(0), "E_CONTROL_DOMAIN");
      return (maximum - minimum) / step;
    }

    function indexOf(value, control, scale) {
      var minimum = parse(control.min, scale);
      var step = parse(control.step, scale);
      var maximumIndex = positions(control, scale);
      var offset = value - minimum;
      invariant(offset >= BigInt(0) && offset % step === BigInt(0), "E_CONTROL_INDEX");
      var index = offset / step;
      invariant(index <= maximumIndex, "E_CONTROL_INDEX");
      return String(index);
    }

    function valueAtIndex(raw, control, scale) {
      invariant(typeof raw === "string" && /^(?:0|[1-9][0-9]*)$/.test(raw), "E_CONTROL_INDEX");
      var index = BigInt(raw);
      var maximumIndex = positions(control, scale);
      invariant(index <= maximumIndex, "E_CONTROL_INDEX");
      return parse(control.min, scale) + index * parse(control.step, scale);
    }

    function grouped(digits) {
      var output = "";
      for (var index = 0; index < digits.length; index += 1) {
        if (index > 0 && (digits.length - index) % 3 === 0) {
          output += ",";
        }
        output += digits.charAt(index);
      }
      return output;
    }

    function format(units, scale, display, precision, delta) {
      var divisor = precision < scale ? power(scale - precision) : BigInt(1);
      var rounded = precision < scale ? roundDiv(units, divisor) : units * power(precision - scale);
      var negative = rounded < BigInt(0);
      var absolute = negative ? -rounded : rounded;
      var digits = String(absolute).padStart(precision + 1, "0");
      var whole = precision ? digits.slice(0, digits.length - precision) : digits;
      var fraction = precision ? "." + digits.slice(digits.length - precision) : "";
      var sign = negative ? "−" : delta && rounded > BigInt(0) ? "+" : "";
      var unit = delta && (display === "%" || display === "percentage_point") ? "pp" : display;
      var number = grouped(whole) + fraction;
      if (unit.charAt(0) === "$" || unit.charAt(0) === "€" || unit.charAt(0) === "£" || unit.charAt(0) === "¥" || unit.charAt(0) === "￥") {
        return sign + unit.charAt(0) + number + unit.slice(1);
      }
      return sign + number + (unit === "%" ? "" : " ") + unit;
    }

    function fraction(value, minimum, maximum) {
      var span = maximum - minimum;
      invariant(span > BigInt(0), "E_GEOMETRY_DOMAIN");
      var bounded = value < minimum ? minimum : value > maximum ? maximum : value;
      var millionths = roundDiv((bounded - minimum) * BigInt(1000000), span);
      return Number(millionths) / 1000000;
    }

    return Object.freeze({ power: power, roundDiv: roundDiv, parse: parse, scaleOf: scaleOf, rescale: rescale, canonical: canonical, snap: snap, positions: positions, indexOf: indexOf, valueAtIndex: valueAtIndex, format: format, fraction: fraction });
  }());

  var DATA = (function () {
    var NARRATION_TEMPLATES = Object.freeze({
      en: Object.freeze({ baseline: "Baseline", reset: "Reset to baseline", restore: "Scenario restored: {count} inputs changed", closed: "Evidence closed", sources: "Sources open", assumptions: "Assumptions open", both: "Sources and assumptions open", openPanel: "{label} open", closePanel: "{label} closed", state: "{label}: {option}; {moved} moved, {changed} changed, {removed} removed" }),
      ja: Object.freeze({ baseline: "初期値", reset: "初期値に戻しました", restore: "シナリオを復元：入力{count}件を変更", closed: "根拠を閉じました", sources: "出典を表示", assumptions: "仮定を表示", both: "出典と仮定を表示", openPanel: "{label}を開きました", closePanel: "{label}を閉じました", state: "{label}：{option}；移動{moved}件、変更{changed}件、除外{removed}件" })
    });

    function decode() {
      invariant(typeof BigInt === "function" && typeof TextDecoder === "function", "E_PLATFORM");
      var node = document.getElementById("idrt-deck-data");
      invariant(node && node.getAttribute("data-encoding") === "base64url-json-v1", "E_DATA_NODE");
      var encoded = node.textContent;
      invariant(encoded.length > 0 && encoded.length <= MAX_ENCODED && /^[A-Za-z0-9_-]+$/.test(encoded) && encoded.length % 4 !== 1, "E_DATA_ENCODING");
      var standard = encoded.replace(/-/g, "+").replace(/_/g, "/");
      standard += "=".repeat((4 - standard.length % 4) % 4);
      var binary = atob(standard);
      invariant(binary.length <= MAX_DECODED, "E_DATA_SIZE");
      var bytes = new Uint8Array(binary.length);
      for (var index = 0; index < binary.length; index += 1) {
        bytes[index] = binary.charCodeAt(index);
      }
      var source = new TextDecoder("utf-8", { fatal: true }).decode(bytes);
      invariant(utf8Length(source) <= MAX_DECODED, "E_DATA_SIZE");
      preflightJson(source);
      return JSON.parse(source);
    }

    function registry(value, validator, code, keyValidator) {
      invariant(plain(value), code);
      var result = new Map();
      var keys = Object.keys(value);
      for (var index = 0; index < keys.length; index += 1) {
        var key = (keyValidator || safeId)(keys[index], code);
        invariant(!result.has(key), code);
        validator(value[key], key);
        result.set(key, value[key]);
      }
      return result;
    }

    function decimal(value, scale, code) {
      var parsed = DECIMAL.parse(value, scale);
      invariant(DECIMAL.canonical(parsed, scale) === value, code);
      return value;
    }

    function decimalAny(value, code) {
      var scale = DECIMAL.scaleOf(value);
      invariant(DECIMAL.canonical(DECIMAL.parse(value, scale), scale) === value, code);
      return value;
    }

    function integer(value, minimum, maximum, code) {
      invariant(Number.isInteger(value) && value >= minimum && value <= maximum, code);
      return value;
    }

    function booleanValue(value, code) {
      invariant(value === true || value === false, code);
      return value;
    }

    function boundedArray(value, maximum, code, minimum) {
      invariant(Array.isArray(value) && value.length <= maximum && value.length >= (minimum || 0), code);
      return value;
    }

    function nonEmptyText(value, code, maximum) {
      text(value, code, maximum);
      invariant(value.length > 0, code);
      return value;
    }

    function unsafeUrlCharacters(value) {
      for (var index = 0; index < value.length; index += 1) {
        var point = value.codePointAt(index);
        if (point > 65535) {
          index += 1;
        }
        if (point < 33 || point === 92 || point === 127 || point === 133 || point === 160 || point === 5760 || (point >= 8192 && point <= 8202) || point === 8232 || point === 8233 || point === 8239 || point === 8287 || point === 12288) {
          return true;
        }
      }
      return false;
    }

    function safeSourceUrl(value) {
      if (typeof value !== "string" || value.length === 0 || scalarLength(value, "E_SOURCE_URL") > 2048 || /%(?![0-9A-Fa-f]{2})/.test(value)) {
        return false;
      }
      var decoded;
      try {
        decoded = decodeURIComponent(value);
      } catch (ignoredDecode) {
        return false;
      }
      if (unsafeUrlCharacters(value) || unsafeUrlCharacters(decoded) || value.indexOf("?") >= 0 || value.indexOf("#") >= 0) {
        return false;
      }
      if (/^mailto:/i.test(value)) {
        var address = value.slice(7);
        if (address.indexOf("%") >= 0) {
          return false;
        }
        var separator = address.indexOf("@");
        if (separator <= 0 || separator !== address.lastIndexOf("@")) {
          return false;
        }
        var local = address.slice(0, separator);
        var domain = address.slice(separator + 1);
        var localParts = local.split(".");
        var localPunctuation = "!#$&'*+/=?^_{|}~-" + String.fromCharCode(96);
        var localValid = localParts.length > 0;
        for (var partIndex = 0; partIndex < localParts.length; partIndex += 1) {
          if (!localParts[partIndex]) {
            localValid = false;
          }
          for (var characterIndex = 0; characterIndex < localParts[partIndex].length; characterIndex += 1) {
            var character = localParts[partIndex].charAt(characterIndex);
            if (!/[A-Za-z0-9]/.test(character) && localPunctuation.indexOf(character) < 0) {
              localValid = false;
            }
          }
        }
        var domainPattern = /^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$/;
        return local.length <= 64 && domain.length <= 253 && localValid && domainPattern.test(domain);
      }
      if (!/^https:\/\//i.test(value)) {
        return false;
      }
      var authorityAndPath = value.slice(value.indexOf("//") + 2);
      var slash = authorityAndPath.indexOf("/");
      var authority = slash < 0 ? authorityAndPath : authorityAndPath.slice(0, slash);
      if (!authority || authority.indexOf("@") >= 0) {
        return false;
      }
      var netlocWithoutSeparators = authority.replace(/[@:#?]/g, "");
      if (netlocWithoutSeparators !== netlocWithoutSeparators.normalize("NFKC") && /[\/?#@:]/.test(netlocWithoutSeparators.normalize("NFKC"))) {
        return false;
      }
      function validPort(portValue) {
        return portValue === "" || (/^[0-9]+$/.test(portValue) && Number(portValue) <= 65535);
      }
      function validUnbracketedHostname(hostValue) {
        for (var hostIndex = 0; hostIndex < hostValue.length; hostIndex += 1) {
          if (hostValue.charCodeAt(hostIndex) > 127) {
            return false;
          }
        }
        if (/^[0-9.]+$/.test(hostValue)) {
          var addressParts = hostValue.split(".");
          if (addressParts.length !== 4) {
            return false;
          }
          for (var addressIndex = 0; addressIndex < addressParts.length; addressIndex += 1) {
            if (!/^(?:0|[1-9][0-9]{0,2})$/.test(addressParts[addressIndex]) || Number(addressParts[addressIndex]) > 255) {
              return false;
            }
          }
          return true;
        }
        var dnsHostname = hostValue.charAt(hostValue.length - 1) === "." ? hostValue.slice(0, -1) : hostValue;
        var labels = dnsHostname.split(".");
        if (!dnsHostname || hostValue.length > 253 || !/[A-Za-z]/.test(labels[labels.length - 1])) {
          return false;
        }
        for (var labelIndex = 0; labelIndex < labels.length; labelIndex += 1) {
          if (!/^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$/.test(labels[labelIndex])) {
            return false;
          }
        }
        return true;
      }
      if (authority.charAt(0) === "[") {
        var closingBracket = authority.indexOf("]");
        if (closingBracket <= 1 || authority.indexOf("[", 1) >= 0 || authority.indexOf("]", closingBracket + 1) >= 0) {
          return false;
        }
        var bracketSuffix = authority.slice(closingBracket + 1);
        if (bracketSuffix && bracketSuffix.charAt(0) !== ":") {
          return false;
        }
        if (!validPort(bracketSuffix ? bracketSuffix.slice(1) : "")) {
          return false;
        }
      } else {
        if (authority.indexOf("[") >= 0 || authority.indexOf("]") >= 0) {
          return false;
        }
        var colon = authority.lastIndexOf(":");
        if (colon >= 0 && authority.indexOf(":") !== colon) {
          return false;
        }
        var hostname = colon < 0 ? authority : authority.slice(0, colon);
        var port = colon < 0 ? "" : authority.slice(colon + 1);
        if (!validUnbracketedHostname(hostname) || !validPort(port)) {
          return false;
        }
      }
      try {
        var parsed = new URL(value);
        return parsed.protocol === "https:" && parsed.hostname.length > 0 && parsed.username === "" && parsed.password === "" && (authority.charAt(0) === "[" || parsed.hostname === hostname.toLowerCase());
      } catch (ignoredHttps) {
        return false;
      }
    }

    function unitId(value, code) {
      invariant(typeof value === "string" && /^[A-Za-z][A-Za-z0-9_]{0,63}$/.test(value) && !SPECIAL.has(value), code);
      return value;
    }

    function textArray(value, maximum, code) {
      boundedArray(value, maximum, code);
      for (var index = 0; index < value.length; index += 1) {
        text(value[index], code, 2000);
      }
      return value;
    }

    function normalization(value, code) {
      var item = exactKeys(value, ["note", "fromUnit", "toUnit"], [], code);
      nonEmptyText(item.note, code, 500);
      nonEmptyText(item.fromUnit, code, 500);
      nonEmptyText(item.toUnit, code, 500);
      return item;
    }

    function validateProvenance(value, code) {
      var item = exactKeys(value, ["basis"], ["sourceRefs", "assumptionRefs", "normalization"], code);
      invariant(["illustrative", "assumed", "estimated", "measured"].indexOf(item.basis) >= 0, code);
      if (own(item, "sourceRefs")) {
        textArray(item.sourceRefs, 20, code);
      }
      if (own(item, "assumptionRefs")) {
        textArray(item.assumptionRefs, 20, code);
      }
      if (own(item, "normalization")) {
        normalization(item.normalization, code);
      }
      return item;
    }

    function validateLineage(value, code) {
      var item = exactKeys(value, ["derived", "badge", "bases", "sourceRefs", "assumptionRefs", "normalizations", "leaves", "steps"], [], code);
      booleanValue(item.derived, code);
      text(item.badge, code, 50);
      var bases = textArray(item.bases, 4, code);
      for (var basisIndex = 0; basisIndex < bases.length; basisIndex += 1) {
        invariant(["illustrative", "assumed", "estimated", "measured"].indexOf(bases[basisIndex]) >= 0, code);
      }
      textArray(item.sourceRefs, 20, code);
      textArray(item.assumptionRefs, 20, code);
      boundedArray(item.normalizations, 20, code);
      for (var normalizationIndex = 0; normalizationIndex < item.normalizations.length; normalizationIndex += 1) {
        normalization(item.normalizations[normalizationIndex], code);
      }
      textArray(item.leaves, 64, code);
      textArray(item.steps, 128, code);
      return item;
    }

    function validateTypedValue(value, scale, code, allowReference) {
      if (allowReference && plain(value) && own(value, "ref")) {
        exactKeys(value, ["ref"], [], code);
        invariant(typeof value.ref === "string" && /^(?:control|output):(?:[a-z][a-z0-9_-]{0,63}|decisionStatus|recommendation|classification|score)$/.test(value.ref), code);
        return value;
      }
      invariant(plain(value) && (value.kind === "numeric" || value.kind === "text"), code);
      if (value.kind === "numeric") {
        var numeric = exactKeys(value, ["kind", "value", "quantity", "lineage"], [], code);
        decimal(numeric.value, scale, code);
        safeId(numeric.quantity, code);
        validateLineage(numeric.lineage, code);
        return numeric;
      }
      var textual = exactKeys(value, ["kind", "value", "lineage"], [], code);
      nonEmptyText(textual.value, code, 2000);
      validateLineage(textual.lineage, code);
      return textual;
    }

    function validateQuantity(quantity, code) {
      var item = exactKeys(quantity, ["dimension", "unit", "exponents", "unitFactors", "display"], ["currency"], code);
      nonEmptyText(item.dimension, code, 64);
      invariant(["scalar", "ratio", "currency", "time", "count", "score", "derived"].indexOf(item.dimension) >= 0, code);
      unitId(item.unit, code);
      nonEmptyText(item.display, code, 12);
      var exponents = exactKeys(item.exponents, ["currency", "time", "count"], [], code);
      integer(exponents.currency, -2, 2, code);
      integer(exponents.time, -2, 2, code);
      integer(exponents.count, -2, 2, code);
      invariant(plain(item.unitFactors) && Object.keys(item.unitFactors).length <= 64, code);
      var factorUnits = Object.keys(item.unitFactors);
      for (var unitIndex = 0; unitIndex < factorUnits.length; unitIndex += 1) {
        unitId(factorUnits[unitIndex], code);
        integer(item.unitFactors[factorUnits[unitIndex]], -2, 2, code);
      }
      if (own(item, "currency")) {
        nonEmptyText(item.currency, code, 3);
        invariant(/^[A-Z]{3}$/.test(item.currency), code);
      }
      return item;
    }

    function validateDotView(value, scale, resolved, code) {
      var view = exactKeys(value, ["component", "xDomain", "xLabel", "xQuantity", "yDomain", "yLabel", "yQuantity", "points"], ["domainReason"], code);
      invariant(view.component === "dot_plot", code);
      var scales = {};
      for (var axisIndex = 0; axisIndex < 2; axisIndex += 1) {
        var axis = axisIndex === 0 ? "x" : "y";
        var domain = boundedArray(view[axis + "Domain"], 2, code, 2);
        invariant(domain.length === 2, code);
        decimalAny(domain[0], code);
        decimalAny(domain[1], code);
        scales[axis] = Math.max(scale, DECIMAL.scaleOf(domain[0]), DECIMAL.scaleOf(domain[1]));
        invariant(DECIMAL.parse(domain[0], scales[axis]) < DECIMAL.parse(domain[1], scales[axis]), code);
        nonEmptyText(view[axis + "Label"], code, 500);
        safeId(view[axis + "Quantity"], code);
      }
      if (own(view, "domainReason")) {
        nonEmptyText(view.domainReason, code, 500);
      }
      boundedArray(view.points, 12, code, 1);
      var pointIds = new Set();
      for (var pointIndex = 0; pointIndex < view.points.length; pointIndex += 1) {
        var required = ["id", "label", "highlight", "removed", "x", "y"];
        if (resolved) {
          required.push("xText", "yText");
        }
        var point = exactKeys(view.points[pointIndex], required, [], code);
        safeId(point.id, code);
        invariant(!pointIds.has(point.id), code);
        pointIds.add(point.id);
        nonEmptyText(point.label, code, 500);
        booleanValue(point.highlight, code);
        booleanValue(point.removed, code);
        validateTypedValue(point.x, scale, code, !resolved);
        validateTypedValue(point.y, scale, code, !resolved);
        if (resolved) {
          text(point.xText, code, 500);
          text(point.yText, code, 500);
        }
      }
      return Object.freeze({ pointIds: pointIds, xScale: scales.x, yScale: scales.y });
    }

    function validateEvidence(value, code) {
      var item = exactKeys(value, ["sources", "assumptions", "leaves", "badge", "formulas", "triggerLabel"], [], code);
      boundedArray(item.sources, 20, code);
      var sourceIds = new Set();
      for (var sourceIndex = 0; sourceIndex < item.sources.length; sourceIndex += 1) {
        var source = exactKeys(item.sources[sourceIndex], ["id", "label", "detail", "linked"], ["url"], code);
        safeId(source.id, code);
        invariant(!sourceIds.has(source.id), code);
        sourceIds.add(source.id);
        nonEmptyText(source.label, code, 500);
        nonEmptyText(source.detail, code, 2000);
        booleanValue(source.linked, code);
        if (own(source, "url")) {
          nonEmptyText(source.url, code, 2048);
        }
        invariant(source.linked === safeSourceUrl(own(source, "url") ? source.url : null), code);
      }
      boundedArray(item.assumptions, 20, code);
      var assumptionIds = new Set();
      for (var assumptionIndex = 0; assumptionIndex < item.assumptions.length; assumptionIndex += 1) {
        var assumption = exactKeys(item.assumptions[assumptionIndex], ["id", "label", "value"], ["unit"], code);
        safeId(assumption.id, code);
        invariant(!assumptionIds.has(assumption.id), code);
        assumptionIds.add(assumption.id);
        nonEmptyText(assumption.label, code, 500);
        nonEmptyText(assumption.value, code, 500);
        if (own(assumption, "unit")) {
          nonEmptyText(assumption.unit, code, 500);
        }
      }
      boundedArray(item.leaves, 64, code);
      var leafIds = new Set();
      for (var leafIndex = 0; leafIndex < item.leaves.length; leafIndex += 1) {
        var leaf = exactKeys(item.leaves[leafIndex], ["id", "label", "quantity", "basis", "sourceRefs", "assumptionRefs"], [], code);
        safeId(leaf.id, code);
        invariant(!leafIds.has(leaf.id), code);
        leafIds.add(leaf.id);
        nonEmptyText(leaf.label, code, 500);
        safeId(leaf.quantity, code);
        invariant(["illustrative", "assumed", "estimated", "measured"].indexOf(leaf.basis) >= 0, code);
        textArray(leaf.sourceRefs, 20, code);
        textArray(leaf.assumptionRefs, 20, code);
      }
      text(item.badge, code, 50);
      textArray(item.formulas, 64, code);
      nonEmptyText(item.triggerLabel, code, 500);
      return Object.freeze({ sourceIds: sourceIds, assumptionIds: assumptionIds, leafIds: leafIds });
    }

    function validateNarration(value, lang, scale, positions, code) {
      var item = exactKeys(value, ["locale", "templates", "templatesByLocale", "messages", "messagesByLocale", "program", "validatedVariants", "comparison", "maxScalars"], [], code);
      invariant(item.locale === lang && item.comparison === "initialState", code);
      invariant(integer(item.maxScalars, 1, 2000, code) === 160, code);
      integer(item.validatedVariants, 0, MAX_NODES, code);
      invariant(BigInt(item.validatedVariants) === (positions + BigInt(1)) * BigInt(4), code);
      var templateKeys = ["baseline", "reset", "restore", "state", "sources", "assumptions", "both", "closed", "openPanel", "closePanel"];
      function textRegistry(valueObject, requiredKeys) {
        invariant(plain(valueObject) && Object.keys(valueObject).length <= 100, code);
        if (requiredKeys) {
          exactKeys(valueObject, requiredKeys, [], code);
        }
        var keys = Object.keys(valueObject);
        for (var registryIndex = 0; registryIndex < keys.length; registryIndex += 1) {
          invariant(!SPECIAL.has(keys[registryIndex]) && keys[registryIndex].length <= 140, code);
          text(valueObject[keys[registryIndex]], code, 500);
          invariant(scalarLength(valueObject[keys[registryIndex]], code) <= item.maxScalars, code);
        }
      }
      var messageKeys = ["evidence:closed", "evidence:sources", "evidence:assumptions", "evidence:both", "panels:closed", "initial", "reset"];
      textRegistry(item.templates, templateKeys);
      textRegistry(item.messages, messageKeys);
      var templatesByLocale = exactKeys(item.templatesByLocale, ["en", "ja"], [], code);
      var messagesByLocale = exactKeys(item.messagesByLocale, ["en", "ja"], [], code);
      textRegistry(templatesByLocale.en, templateKeys);
      textRegistry(templatesByLocale.ja, templateKeys);
      textRegistry(messagesByLocale.en, messageKeys);
      textRegistry(messagesByLocale.ja, messageKeys);
      for (var localeIndex = 0; localeIndex < 2; localeIndex += 1) {
        var locale = localeIndex === 0 ? "en" : "ja";
        for (var fixedTemplateIndex = 0; fixedTemplateIndex < templateKeys.length; fixedTemplateIndex += 1) {
          var fixedTemplateKey = templateKeys[fixedTemplateIndex];
          invariant(templatesByLocale[locale][fixedTemplateKey] === NARRATION_TEMPLATES[locale][fixedTemplateKey], code);
        }
      }
      var activeTemplates = templatesByLocale[lang];
      var activeMessages = messagesByLocale[lang];
      for (var templateIndex = 0; templateIndex < templateKeys.length; templateIndex += 1) {
        invariant(item.templates[templateKeys[templateIndex]] === activeTemplates[templateKeys[templateIndex]], code);
      }
      for (var messageIndex = 0; messageIndex < messageKeys.length; messageIndex += 1) {
        invariant(item.messages[messageKeys[messageIndex]] === activeMessages[messageKeys[messageIndex]], code);
      }
      var program = exactKeys(item.program, ["kind", "controls", "outputs", "transitions"], [], code);
      invariant(program.kind === "numeric_delta_v1", code);
      boundedArray(program.controls, 8, code);
      for (var controlIndex = 0; controlIndex < program.controls.length; controlIndex += 1) {
        var control = exactKeys(program.controls[controlIndex], ["baseline", "display", "id", "kind", "label", "precision", "unit"], [], code);
        invariant(control.kind === "range", code);
        safeId(control.id, code);
        decimal(control.baseline, scale, code);
        text(control.display, code, 500);
        text(control.label, code, 500);
        text(control.unit, code, 500);
        integer(control.precision, 0, 6, code);
      }
      boundedArray(program.outputs, 3, code);
      for (var outputIndex = 0; outputIndex < program.outputs.length; outputIndex += 1) {
        var output = exactKeys(program.outputs[outputIndex], ["baseline", "display", "id", "label", "precision", "unit"], [], code);
        outputId(output.id, code);
        decimal(output.baseline, scale, code);
        text(output.display, code, 500);
        text(output.label, code, 500);
        text(output.unit, code, 500);
        integer(output.precision, 0, 6, code);
      }
      boundedArray(program.transitions, 2, code);
      for (var transitionIndex = 0; transitionIndex < program.transitions.length; transitionIndex += 1) {
        var transition = exactKeys(program.transitions[transitionIndex], ["baseline", "id"], [], code);
        outputId(transition.id, code);
        text(transition.baseline, code, 500);
      }
      return program;
    }

    function validateTask4Scene(scene, slideId, lang, ordinal) {
      var rationaleKey = "interaction" + "Rationale";
      exactKeys(scene, ["version", "slideId", "type", "locale", "scale", "purpose", "decisionJob", rationaleKey, "initialState", "printState", "controls", "quantities", "outputDefinitions", "evidence", "invariants", "fallback", "targets", "steps", "narration", "initialEvaluation", "model", "reporting", "decisionContract", "view"], [], "E_SCENE_SHAPE");
      invariant(scene.version === 1 && scene.slideId === slideId && scene.type === "slider_model" && scene.locale === lang, "E_SCENE_IDENTITY");
      invariant(Number.isInteger(scene.scale) && scene.scale >= 0 && scene.scale <= 6, "E_SCENE_SCALE");
      nonEmptyText(scene.purpose, "E_SCENE_TEXT", 500);
      nonEmptyText(scene[rationaleKey], "E_SCENE_TEXT", 500);
      invariant(["fact", "insight", "action", "decision"].indexOf(scene.decisionJob) >= 0, "E_SCENE_TEXT");
      invariant(Array.isArray(scene.controls) && scene.controls.length === 1, "E_CONTROL_SHAPE");
      var control = exactKeys(scene.controls[0], ["id", "kind", "label", "min", "max", "step", "quantity", "lineage"], [], "E_CONTROL_SHAPE");
      safeId(control.id, "E_CONTROL_ID");
      invariant(control.kind === "range", "E_CONTROL_KIND");
      text(control.label, "E_CONTROL_LABEL", 40);
      decimal(control.min, scene.scale, "E_CONTROL_DOMAIN");
      decimal(control.max, scene.scale, "E_CONTROL_DOMAIN");
      decimal(control.step, scene.scale, "E_CONTROL_DOMAIN");
      var minimum = DECIMAL.parse(control.min, scene.scale);
      var maximum = DECIMAL.parse(control.max, scene.scale);
      var step = DECIMAL.parse(control.step, scene.scale);
      invariant(minimum < maximum && step > BigInt(0) && (maximum - minimum) % step === BigInt(0) && (maximum - minimum) / step <= BigInt(10000), "E_CONTROL_DOMAIN");
      safeId(control.quantity, "E_QUANTITY_ID");
      validateLineage(control.lineage, "E_CONTROL_LINEAGE");
      exactKeys(scene.initialState, [control.id], [], "E_INITIAL_STATE");
      exactKeys(scene.printState, [control.id], [], "E_PRINT_STATE");
      decimal(scene.initialState[control.id], scene.scale, "E_INITIAL_STATE");
      invariant(scene.printState[control.id] === scene.initialState[control.id], "E_PRINT_STATE");
      var initialControl = DECIMAL.parse(scene.initialState[control.id], scene.scale);
      invariant(initialControl >= minimum && initialControl <= maximum && (initialControl - minimum) % step === BigInt(0), "E_INITIAL_STATE");

      invariant(Object.keys(scene.quantities).length <= 64, "E_QUANTITY_REGISTRY");
      var quantities = registry(scene.quantities, function (quantity) {
        validateQuantity(quantity, "E_QUANTITY_SHAPE");
      }, "E_QUANTITY_REGISTRY");
      invariant(quantities.has(control.quantity), "E_QUANTITY_REFERENCE");
      invariant(plain(scene.outputDefinitions) && Object.keys(scene.outputDefinitions).length <= 64, "E_OUTPUT_REGISTRY");
      var definitions = registry(scene.outputDefinitions, function (definition) {
        if (definition.kind === "numeric") {
          exactKeys(definition, ["kind", "label", "quantity", "format", "round"], [], "E_OUTPUT_SHAPE");
          safeId(definition.quantity, "E_QUANTITY_ID");
          nonEmptyText(definition.label, "E_OUTPUT_SHAPE", 40);
          invariant(quantities.has(definition.quantity) && ["number", "percent", "currency", "duration", "score"].indexOf(definition.format) >= 0, "E_OUTPUT_SHAPE");
          integer(definition.round, 0, 6, "E_OUTPUT_SHAPE");
        } else {
          exactKeys(definition, ["kind", "label"], [], "E_OUTPUT_SHAPE");
          invariant(definition.kind === "text", "E_OUTPUT_SHAPE");
          nonEmptyText(definition.label, "E_OUTPUT_SHAPE", 500);
        }
      }, "E_OUTPUT_REGISTRY", outputId);

      exactKeys(scene.model, ["kind", "output", "intercept", "terms"], [], "E_MODEL_SHAPE");
      invariant(scene.model.kind === "linear" && definitions.has(scene.model.output) && definitions.get(scene.model.output).kind === "numeric", "E_MODEL_KIND");
      validateTypedValue(scene.model.intercept, scene.scale, "E_MODEL_SHAPE", false);
      invariant(Array.isArray(scene.model.terms) && scene.model.terms.length === 1 && Array.isArray(scene.model.terms[0]) && scene.model.terms[0].length === 2, "E_MODEL_SHAPE");
      invariant(scene.model.terms[0][0] === control.id, "E_MODEL_REFERENCE");
      var term = exactKeys(scene.model.terms[0][1], ["value", "inputQuantity", "outputQuantity"], [], "E_MODEL_SHAPE");
      validateTypedValue(term.value, scene.scale, "E_MODEL_SHAPE", false);
      safeId(term.inputQuantity, "E_MODEL_SHAPE");
      safeId(term.outputQuantity, "E_MODEL_SHAPE");
      invariant(scene.model.intercept.kind === "numeric" && scene.model.intercept.quantity === definitions.get(scene.model.output).quantity, "E_MODEL_REFERENCE");
      invariant(term.value.kind === "numeric" && term.inputQuantity === control.quantity && term.outputQuantity === definitions.get(scene.model.output).quantity && term.value.quantity === term.outputQuantity, "E_MODEL_REFERENCE");
      invariant(quantities.has(term.inputQuantity) && quantities.has(term.outputQuantity) && quantities.has(term.value.quantity), "E_MODEL_REFERENCE");

      exactKeys(scene.reporting, ["primaryOutput", "secondaryOutputs"], [], "E_REPORTING_SHAPE");
      invariant(scene.reporting.primaryOutput === scene.model.output && Array.isArray(scene.reporting.secondaryOutputs) && scene.reporting.secondaryOutputs.length === 0, "E_REPORTING_SHAPE");
      exactKeys(scene.decisionContract, ["id", "metric", "operator", "threshold", "whenMet", "whenNotMet"], [], "E_DECISION_SHAPE");
      safeId(scene.decisionContract.id, "E_DECISION_SHAPE");
      exactKeys(scene.decisionContract.metric, ["ref"], [], "E_DECISION_SHAPE");
      invariant(scene.decisionContract.metric.ref === "output:" + scene.model.output, "E_DECISION_REFERENCE");
      invariant(["gte", "gt", "lte", "lt"].indexOf(scene.decisionContract.operator) >= 0, "E_DECISION_OPERATOR");
      exactKeys(scene.decisionContract.threshold, ["value", "quantity", "provenance"], [], "E_DECISION_SHAPE");
      decimal(scene.decisionContract.threshold.value, scene.scale, "E_DECISION_SHAPE");
      safeId(scene.decisionContract.threshold.quantity, "E_DECISION_SHAPE");
      invariant(scene.decisionContract.threshold.quantity === definitions.get(scene.model.output).quantity && quantities.has(scene.decisionContract.threshold.quantity), "E_DECISION_REFERENCE");
      validateProvenance(scene.decisionContract.threshold.provenance, "E_DECISION_SHAPE");
      exactKeys(scene.decisionContract.whenMet, ["status", "recommendation"], [], "E_DECISION_SHAPE");
      exactKeys(scene.decisionContract.whenNotMet, ["status", "recommendation"], [], "E_DECISION_SHAPE");
      nonEmptyText(scene.decisionContract.whenMet.status, "E_DECISION_SHAPE", 32);
      nonEmptyText(scene.decisionContract.whenMet.recommendation, "E_DECISION_SHAPE", 500);
      nonEmptyText(scene.decisionContract.whenNotMet.status, "E_DECISION_SHAPE", 32);
      nonEmptyText(scene.decisionContract.whenNotMet.recommendation, "E_DECISION_SHAPE", 500);

      var viewInfo = validateDotView(scene.view, scene.scale, false, "E_VIEW_SHAPE");
      invariant(quantities.has(scene.view.xQuantity) && quantities.has(scene.view.yQuantity), "E_VIEW_REFERENCE");
      var pointIds = new Set();
      var outputAxes = new Set();
      function pointSlot(slot, axisQuantity) {
        if (plain(slot) && own(slot, "ref")) {
          exactKeys(slot, ["ref"], [], "E_VIEW_REFERENCE");
          if (slot.ref === "control:" + control.id) {
            invariant(control.quantity === axisQuantity, "E_VIEW_REFERENCE");
          } else if (slot.ref === "output:" + scene.model.output) {
            invariant(definitions.get(scene.model.output).quantity === axisQuantity, "E_VIEW_REFERENCE");
          } else {
            invariant(false, "E_VIEW_REFERENCE");
          }
          return;
        }
        validateTypedValue(slot, scene.scale, "E_VIEW_VALUE", false);
        invariant(slot.kind === "numeric" && slot.quantity === axisQuantity, "E_VIEW_VALUE");
      }
      for (var pointIndex = 0; pointIndex < scene.view.points.length; pointIndex += 1) {
        var point = exactKeys(scene.view.points[pointIndex], ["id", "label", "highlight", "removed", "x", "y"], [], "E_VIEW_POINT");
        safeId(point.id, "E_VIEW_POINT");
        invariant(!pointIds.has(point.id) && point.removed === false, "E_VIEW_POINT");
        pointIds.add(point.id);
        pointSlot(point.x, scene.view.xQuantity);
        pointSlot(point.y, scene.view.yQuantity);
        if (plain(point.x) && point.x.ref === "output:" + scene.model.output) {
          outputAxes.add("x");
        }
        if (plain(point.y) && point.y.ref === "output:" + scene.model.output) {
          outputAxes.add("y");
        }
      }
      invariant(outputAxes.size === 1, "E_VIEW_REFERENCE");

      exactKeys(scene.initialEvaluation, ["outputs", "view", "decision"], [], "E_INITIAL_EVALUATION");
      var initialOutputs = registry(scene.initialEvaluation.outputs, function (output) {
        validateTypedValue(output, scene.scale, "E_INITIAL_OUTPUT", false);
      }, "E_INITIAL_OUTPUTS", outputId);
      invariant(initialOutputs.size === definitions.size && initialOutputs.has(scene.model.output) && initialOutputs.has("decisionStatus") && initialOutputs.has("recommendation"), "E_INITIAL_OUTPUTS");
      definitions.forEach(function (definition, outputKey) { invariant(initialOutputs.has(outputKey), "E_INITIAL_OUTPUTS"); });
      decimal(initialOutputs.get(scene.model.output).value, scene.scale, "E_INITIAL_OUTPUT");
      exactKeys(scene.initialEvaluation.decision, ["outcome", "distance", "quantity", "status", "recommendation", "lineage"], [], "E_INITIAL_DECISION");
      invariant(["met", "notMet"].indexOf(scene.initialEvaluation.decision.outcome) >= 0, "E_INITIAL_DECISION");
      decimal(scene.initialEvaluation.decision.distance, scene.scale, "E_INITIAL_DECISION");
      safeId(scene.initialEvaluation.decision.quantity, "E_INITIAL_DECISION");
      nonEmptyText(scene.initialEvaluation.decision.status, "E_INITIAL_DECISION", 500);
      nonEmptyText(scene.initialEvaluation.decision.recommendation, "E_INITIAL_DECISION", 500);
      validateLineage(scene.initialEvaluation.decision.lineage, "E_INITIAL_DECISION");
      var evaluatedViewInfo = validateDotView(scene.initialEvaluation.view, scene.scale, true, "E_INITIAL_VIEW");
      invariant(evaluatedViewInfo.pointIds.size === viewInfo.pointIds.size, "E_INITIAL_VIEW");
      viewInfo.pointIds.forEach(function (pointId) { invariant(evaluatedViewInfo.pointIds.has(pointId), "E_INITIAL_VIEW"); });
      invariant(scene.initialEvaluation.view.component === scene.view.component && scene.initialEvaluation.view.xLabel === scene.view.xLabel && scene.initialEvaluation.view.xQuantity === scene.view.xQuantity && scene.initialEvaluation.view.yLabel === scene.view.yLabel && scene.initialEvaluation.view.yQuantity === scene.view.yQuantity && JSON.stringify(scene.initialEvaluation.view.xDomain) === JSON.stringify(scene.view.xDomain) && JSON.stringify(scene.initialEvaluation.view.yDomain) === JSON.stringify(scene.view.yDomain) && (scene.initialEvaluation.view.domainReason || null) === (scene.view.domainReason || null), "E_INITIAL_VIEW");
      invariant(scene.initialEvaluation.view.points.length === scene.view.points.length, "E_INITIAL_VIEW");
      for (var evaluatedPointIndex = 0; evaluatedPointIndex < scene.view.points.length; evaluatedPointIndex += 1) {
        var sourceViewPoint = scene.view.points[evaluatedPointIndex];
        var evaluatedViewPoint = scene.initialEvaluation.view.points[evaluatedPointIndex];
        invariant(sourceViewPoint.id === evaluatedViewPoint.id && sourceViewPoint.label === evaluatedViewPoint.label && sourceViewPoint.highlight === evaluatedViewPoint.highlight && sourceViewPoint.removed === evaluatedViewPoint.removed, "E_INITIAL_VIEW");
      }
      var positions = DECIMAL.positions(control, scene.scale);
      var narrationProgram = validateNarration(scene.narration, lang, scene.scale, positions, "E_NARRATION_SHAPE");
      var narrationControl = narrationProgram.controls[0];
      var controlQuantity = quantities.get(control.quantity);
      invariant(narrationProgram.controls.length === 1 && narrationControl.id === control.id && narrationControl.kind === control.kind && narrationControl.label === control.label && narrationControl.baseline === scene.initialState[control.id] && narrationControl.unit === controlQuantity.unit && narrationControl.display === controlQuantity.display && narrationControl.precision === scene.scale, "E_NARRATION_REFERENCE");
      var narrationOutput = narrationProgram.outputs[0];
      var outputDefinition = definitions.get(scene.model.output);
      var outputQuantity = quantities.get(outputDefinition.quantity);
      invariant(narrationProgram.outputs.length === 1 && narrationOutput.id === scene.model.output && narrationOutput.label === outputDefinition.label && narrationOutput.baseline === initialOutputs.get(scene.model.output).value && narrationOutput.unit === outputQuantity.unit && narrationOutput.display === outputQuantity.display && narrationOutput.precision === outputDefinition.round, "E_NARRATION_REFERENCE");
      invariant(narrationProgram.transitions.length === 1 && narrationProgram.transitions[0].id === "decisionStatus" && narrationProgram.transitions[0].baseline === scene.initialEvaluation.decision.status, "E_NARRATION_REFERENCE");
      var primaryText = outputDefinition.label + " " + DECIMAL.format(DECIMAL.parse(initialOutputs.get(scene.model.output).value, scene.scale), scene.scale, outputQuantity.display, outputDefinition.round, false);
      for (var narrationLocaleIndex = 0; narrationLocaleIndex < 2; narrationLocaleIndex += 1) {
        var narrationLocale = narrationLocaleIndex === 0 ? "en" : "ja";
        var fixedTemplates = NARRATION_TEMPLATES[narrationLocale];
        var expectedMessages = {
          "evidence:closed": fixedTemplates.closed,
          "evidence:sources": fixedTemplates.sources,
          "evidence:assumptions": fixedTemplates.assumptions,
          "evidence:both": fixedTemplates.both,
          "panels:closed": narrationLocale === "ja" ? "説明を閉じました" : "Panels closed",
          initial: fixedTemplates.baseline + ": " + primaryText + "; " + scene.initialEvaluation.decision.status,
          reset: fixedTemplates.reset + ": " + primaryText + "; " + scene.initialEvaluation.decision.status
        };
        var actualMessages = scene.narration.messagesByLocale[narrationLocale];
        var expectedMessageKeys = Object.keys(expectedMessages);
        for (var expectedMessageIndex = 0; expectedMessageIndex < expectedMessageKeys.length; expectedMessageIndex += 1) {
          var expectedMessageKey = expectedMessageKeys[expectedMessageIndex];
          invariant(actualMessages[expectedMessageKey] === expectedMessages[expectedMessageKey], "E_NARRATION_REFERENCE");
        }
      }
      invariant(initialOutputs.get("decisionStatus").kind === "text" && initialOutputs.get("decisionStatus").value === scene.initialEvaluation.decision.status && initialOutputs.get("recommendation").kind === "text" && initialOutputs.get("recommendation").value === scene.initialEvaluation.decision.recommendation, "E_INITIAL_OUTPUTS");
      var evidenceInfo = validateEvidence(scene.evidence, "E_EVIDENCE_SHAPE");
      var expectedFormula = definitions.get(scene.model.output).label + " = " + DECIMAL.canonical(DECIMAL.parse(scene.model.intercept.value, scene.scale), scene.scale) + " + " + DECIMAL.canonical(DECIMAL.parse(term.value.value, scene.scale), scene.scale) + " × " + control.label;
      invariant(scene.evidence.formulas.length === 1 && scene.evidence.formulas[0] === expectedFormula, "E_EVIDENCE_REFERENCE");
      function validateLineageReferences(lineage) {
        for (var sourceRefIndex = 0; sourceRefIndex < lineage.sourceRefs.length; sourceRefIndex += 1) {
          safeId(lineage.sourceRefs[sourceRefIndex], "E_LINEAGE_REFERENCE");
          invariant(evidenceInfo.sourceIds.has(lineage.sourceRefs[sourceRefIndex]), "E_LINEAGE_REFERENCE");
        }
        for (var assumptionRefIndex = 0; assumptionRefIndex < lineage.assumptionRefs.length; assumptionRefIndex += 1) {
          safeId(lineage.assumptionRefs[assumptionRefIndex], "E_LINEAGE_REFERENCE");
          invariant(evidenceInfo.assumptionIds.has(lineage.assumptionRefs[assumptionRefIndex]), "E_LINEAGE_REFERENCE");
        }
        for (var leafRefIndex = 0; leafRefIndex < lineage.leaves.length; leafRefIndex += 1) {
          safeId(lineage.leaves[leafRefIndex], "E_LINEAGE_REFERENCE");
          invariant(evidenceInfo.leafIds.has(lineage.leaves[leafRefIndex]), "E_LINEAGE_REFERENCE");
        }
      }
      validateLineageReferences(control.lineage);
      validateLineageReferences(scene.model.intercept.lineage);
      validateLineageReferences(term.value.lineage);
      initialOutputs.forEach(function (outputValue) { validateLineageReferences(outputValue.lineage); });
      validateLineageReferences(scene.initialEvaluation.decision.lineage);
      for (var evidenceLeafIndex = 0; evidenceLeafIndex < scene.evidence.leaves.length; evidenceLeafIndex += 1) {
        var evidenceLeaf = scene.evidence.leaves[evidenceLeafIndex];
        invariant(quantities.has(evidenceLeaf.quantity), "E_EVIDENCE_REFERENCE");
        for (var leafSourceIndex = 0; leafSourceIndex < evidenceLeaf.sourceRefs.length; leafSourceIndex += 1) {
          invariant(evidenceInfo.sourceIds.has(evidenceLeaf.sourceRefs[leafSourceIndex]), "E_EVIDENCE_REFERENCE");
        }
        for (var leafAssumptionIndex = 0; leafAssumptionIndex < evidenceLeaf.assumptionRefs.length; leafAssumptionIndex += 1) {
          invariant(evidenceInfo.assumptionIds.has(evidenceLeaf.assumptionRefs[leafAssumptionIndex]), "E_EVIDENCE_REFERENCE");
        }
      }
      var thresholdProvenance = scene.decisionContract.threshold.provenance;
      var provenanceSources = thresholdProvenance.sourceRefs || [];
      var provenanceAssumptions = thresholdProvenance.assumptionRefs || [];
      for (var provenanceSourceIndex = 0; provenanceSourceIndex < provenanceSources.length; provenanceSourceIndex += 1) {
        safeId(provenanceSources[provenanceSourceIndex], "E_EVIDENCE_REFERENCE");
        invariant(evidenceInfo.sourceIds.has(provenanceSources[provenanceSourceIndex]), "E_EVIDENCE_REFERENCE");
      }
      for (var provenanceAssumptionIndex = 0; provenanceAssumptionIndex < provenanceAssumptions.length; provenanceAssumptionIndex += 1) {
        safeId(provenanceAssumptions[provenanceAssumptionIndex], "E_EVIDENCE_REFERENCE");
        invariant(evidenceInfo.assumptionIds.has(provenanceAssumptions[provenanceAssumptionIndex]), "E_EVIDENCE_REFERENCE");
      }
      for (var viewPointIndex = 0; viewPointIndex < scene.view.points.length; viewPointIndex += 1) {
        var unresolvedPoint = scene.view.points[viewPointIndex];
        if (!own(unresolvedPoint.x, "ref")) { validateLineageReferences(unresolvedPoint.x.lineage); }
        if (!own(unresolvedPoint.y, "ref")) { validateLineageReferences(unresolvedPoint.y.lineage); }
        validateLineageReferences(scene.initialEvaluation.view.points[viewPointIndex].x.lineage);
        validateLineageReferences(scene.initialEvaluation.view.points[viewPointIndex].y.lineage);
      }
      invariant(plain(scene.invariants), "E_INVARIANTS_SHAPE");
      var invariantKeys = Object.keys(scene.invariants);
      var allowedInvariants = new Set(["headline", "subline", "source", "footnotes", "eyebrow", "section", "page_number", "classification", "lang", "theme", "palette"]);
      for (var invariantIndex = 0; invariantIndex < invariantKeys.length; invariantIndex += 1) {
        var invariantKey = invariantKeys[invariantIndex];
        invariant(allowedInvariants.has(invariantKey) && !SPECIAL.has(invariantKey), "E_INVARIANTS_SHAPE");
        if (invariantKey === "footnotes") {
          textArray(scene.invariants[invariantKey], 2, "E_INVARIANTS_SHAPE");
        } else {
          text(scene.invariants[invariantKey], "E_INVARIANTS_SHAPE", 500);
        }
      }
      invariant(!own(scene.invariants, "theme") || ["classic", "executive"].indexOf(scene.invariants.theme) >= 0, "E_INVARIANTS_SHAPE");
      invariant(!own(scene.invariants, "palette") || ["navy", "red", "green", "mono"].indexOf(scene.invariants.palette) >= 0, "E_INVARIANTS_SHAPE");
      var fallback = exactKeys(scene.fallback, ["matched", "pattern"], [], "E_FALLBACK_SHAPE");
      invariant(fallback.matched === true && fallback.pattern === "scatter", "E_FALLBACK_SHAPE");
      var targets = new Map();
      var targetKeys = Object.keys(scene.targets);
      invariant(plain(scene.targets) && targetKeys.length <= MAX_TARGETS, "E_TARGET_REGISTRY");
      for (var targetIndex = 0; targetIndex < targetKeys.length; targetIndex += 1) {
        var targetKey = targetKeys[targetIndex];
        nonEmptyText(targetKey, "E_TARGET_REGISTRY", 140);
        invariant(!targets.has(targetKey) && !SPECIAL.has(targetKey), "E_TARGET_REGISTRY");
        var target = exactKeys(scene.targets[targetKey], ["kind"], ["id"], "E_TARGET_REGISTRY");
        invariant(["control", "source", "evidence", "static"].indexOf(target.kind) >= 0, "E_TARGET_REGISTRY");
        if (target.kind === "control") {
          invariant(target.id === control.id && targetKey === "control:" + control.id, "E_TARGET_REGISTRY");
        } else if (target.kind === "source") {
          safeId(target.id, "E_TARGET_REGISTRY");
          invariant(evidenceInfo.sourceIds.has(target.id) && targetKey === "source:" + target.id, "E_TARGET_REGISTRY");
        } else {
          invariant(!own(target, "id"), "E_TARGET_REGISTRY");
          invariant((target.kind === "evidence" && (targetKey === "evidence:open" || targetKey === "evidence:close")) || (target.kind === "static" && targetKey === "static:toggle"), "E_TARGET_REGISTRY");
        }
        targets.set(targetKey, target);
      }
      invariant(targets.has("evidence:open") && targets.get("evidence:open").kind === "evidence", "E_TARGET_REGISTRY");
      invariant(targets.has("evidence:close") && targets.get("evidence:close").kind === "evidence", "E_TARGET_REGISTRY");
      invariant(targets.has("static:toggle") && targets.get("static:toggle").kind === "static", "E_TARGET_REGISTRY");
      invariant(targets.has("control:" + control.id), "E_TARGET_REGISTRY");
      for (var sourceIndex = 0; sourceIndex < scene.evidence.sources.length; sourceIndex += 1) {
        var evidenceSource = scene.evidence.sources[sourceIndex];
        invariant(evidenceSource.linked === targets.has("source:" + evidenceSource.id), "E_TARGET_REGISTRY");
      }
      var expectedTargetCount = 4;
      for (var linkedSourceIndex = 0; linkedSourceIndex < scene.evidence.sources.length; linkedSourceIndex += 1) {
        if (scene.evidence.sources[linkedSourceIndex].linked) {
          expectedTargetCount += 1;
        }
      }
      invariant(targets.size === expectedTargetCount, "E_TARGET_REGISTRY");
      var stepKeys = new Set();
      var gotoIds = [];
      var waitMs = 0;
      boundedArray(scene.steps, 80, "E_STEP_SHAPE");
      for (var stepIndex = 0; stepIndex < scene.steps.length; stepIndex += 1) {
        var stepRecord = exactKeys(scene.steps[stepIndex], ["stepKey", "action"], ["targetKey"], "E_STEP_SHAPE");
        safeId(stepRecord.stepKey, "E_STEP_SHAPE");
        invariant(!stepKeys.has(stepRecord.stepKey), "E_STEP_SHAPE");
        stepKeys.add(stepRecord.stepKey);
        invariant(plain(stepRecord.action) && typeof stepRecord.action.type === "string", "E_STEP_SHAPE");
        var action = stepRecord.action;
        var expectedTarget = null;
        if (action.type === "set") {
          exactKeys(action, ["type", "control", "value"], [], "E_STEP_SHAPE");
          invariant(action.control === control.id, "E_STEP_SHAPE");
          var stepValue = DECIMAL.parse(action.value, scene.scale);
          invariant(stepValue >= minimum && stepValue <= maximum && (stepValue - minimum) % step === BigInt(0), "E_STEP_SHAPE");
          expectedTarget = "control:" + action.control;
        } else if (action.type === "openEvidence" || action.type === "closeEvidence") {
          exactKeys(action, ["type"], [], "E_STEP_SHAPE");
          expectedTarget = action.type === "openEvidence" ? "evidence:open" : "evidence:close";
        } else if (action.type === "goto") {
          exactKeys(action, ["type", "slideId"], [], "E_STEP_SHAPE");
          safeId(action.slideId, "E_STEP_SHAPE");
          gotoIds.push(action.slideId);
        } else if (action.type === "wait") {
          exactKeys(action, ["type", "ms"], [], "E_STEP_SHAPE");
          waitMs += integer(action.ms, 0, 5000, "E_STEP_SHAPE");
        } else {
          invariant(false, "E_STEP_SHAPE");
        }
        if (expectedTarget === null) {
          invariant(!own(stepRecord, "targetKey"), "E_STEP_SHAPE");
        } else {
          invariant(stepRecord.targetKey === expectedTarget && targets.has(expectedTarget), "E_STEP_SHAPE");
        }
      }
      invariant(waitMs <= 30000, "E_STEP_SHAPE");
      deepFreeze(scene);
      var legacyControls = new Map([[control.id, control]]);
      var legacyValues = [];
      for (var legacyValueIndex = BigInt(0); legacyValueIndex <= positions; legacyValueIndex += BigInt(1)) {
        legacyValues.push(DECIMAL.canonical(DECIMAL.valueAtIndex(String(legacyValueIndex), control, scene.scale), scene.scale));
      }
      return Object.freeze({ ordinal: ordinal, type: scene.type, scene: scene, control: control, controls: legacyControls, controlList: Object.freeze([control]), controlDomains: new Map([[control.id, Object.freeze(legacyValues)]]), quantities: quantities, definitions: definitions, targets: targets, acceptedStates: Number(positions + BigInt(1)), viewItems: scene.view.points.length + scene.initialEvaluation.view.points.length, stepCount: scene.steps.length, waitMs: waitMs, gotoIds: Object.freeze(gotoIds), xScale: viewInfo.xScale, yScale: viewInfo.yScale });
    }

    function validateTask5Fallback(value) {
      var fallback = exactKeys(value, ["matched", "pattern", "paragraphs", "baselineAnnotation", "thresholdText", "axisTickLabels"], [], "E_FALLBACK_SHAPE");
      invariant(fallback.matched === true, "E_FALLBACK_SHAPE");
      nonEmptyText(fallback.pattern, "E_FALLBACK_SHAPE", 64);
      boundedArray(fallback.paragraphs, 1000, "E_FALLBACK_SHAPE");
      for (var paragraphIndex = 0; paragraphIndex < fallback.paragraphs.length; paragraphIndex += 1) {
        text(fallback.paragraphs[paragraphIndex], "E_FALLBACK_SHAPE", 2000);
      }
      text(fallback.baselineAnnotation, "E_FALLBACK_SHAPE", 2000);
      if (fallback.thresholdText !== null) { text(fallback.thresholdText, "E_FALLBACK_SHAPE", 500); }
      if (fallback.axisTickLabels !== null) {
        exactKeys(fallback.axisTickLabels, ["x", "y"], [], "E_FALLBACK_SHAPE");
        for (var fallbackAxisIndex = 0; fallbackAxisIndex < 2; fallbackAxisIndex += 1) {
          var fallbackAxis = fallbackAxisIndex === 0 ? "x" : "y";
          invariant(Array.isArray(fallback.axisTickLabels[fallbackAxis]) && fallback.axisTickLabels[fallbackAxis].length === 2, "E_FALLBACK_SHAPE");
          text(fallback.axisTickLabels[fallbackAxis][0], "E_FALLBACK_SHAPE", 500);
          text(fallback.axisTickLabels[fallbackAxis][1], "E_FALLBACK_SHAPE", 500);
        }
      }
      return fallback;
    }

    function validateEvidenceScene(scene, slideId, lang, ordinal) {
      var rationaleKey = "interaction" + "Rationale";
      exactKeys(scene, ["version", "slideId", "type", "locale", "scale", "purpose", "decisionJob", rationaleKey, "initialState", "printState", "controls", "quantities", "outputDefinitions", "evidence", "invariants", "fallback", "targets", "steps", "narration", "initialEvaluation"], [], "E_SCENE_SHAPE");
      invariant(scene.version === 1 && scene.slideId === slideId && scene.type === "evidence_only" && scene.locale === lang && scene.scale === 0, "E_SCENE_IDENTITY");
      nonEmptyText(scene.purpose, "E_SCENE_TEXT", 500);
      nonEmptyText(scene[rationaleKey], "E_SCENE_TEXT", 500);
      invariant(["fact", "insight", "action", "decision"].indexOf(scene.decisionJob) >= 0, "E_SCENE_TEXT");
      invariant(Array.isArray(scene.controls) && scene.controls.length === 0 && plain(scene.quantities) && Object.keys(scene.quantities).length === 0 && plain(scene.outputDefinitions) && Object.keys(scene.outputDefinitions).length === 0, "E_SCENE_SHAPE");
      var evidenceInfo = validateEvidence(scene.evidence, "E_EVIDENCE_SHAPE");
      var modes = new Set(["closed"]);
      if (scene.evidence.sources.length) { modes.add("sources"); }
      if (scene.evidence.assumptions.length) { modes.add("assumptions"); }
      if (scene.evidence.sources.length && scene.evidence.assumptions.length) { modes.add("both"); }
      exactKeys(scene.initialState, ["evidence"], [], "E_INITIAL_STATE");
      exactKeys(scene.printState, ["evidence"], [], "E_PRINT_STATE");
      invariant(modes.has(scene.initialState.evidence) && scene.printState.evidence === scene.initialState.evidence, "E_INITIAL_STATE");
      exactKeys(scene.initialEvaluation, ["outputs", "view"], [], "E_INITIAL_EVALUATION");
      invariant(plain(scene.initialEvaluation.outputs) && Object.keys(scene.initialEvaluation.outputs).length === 0 && scene.initialEvaluation.view === null, "E_INITIAL_EVALUATION");
      invariant(plain(scene.invariants) && Object.keys(scene.invariants).length <= 11, "E_INVARIANTS_SHAPE");
      validateTask5Fallback(scene.fallback);
      var narration = exactKeys(scene.narration, ["locale", "templates", "templatesByLocale", "messages", "messagesByLocale", "program", "validatedVariants", "comparison", "maxScalars"], [], "E_NARRATION_SHAPE");
      invariant(narration.locale === lang && narration.comparison === "initialState" && narration.maxScalars === 160 && Number.isInteger(narration.validatedVariants), "E_NARRATION_SHAPE");
      var program = exactKeys(narration.program, ["kind", "stateKey"], [], "E_NARRATION_SHAPE");
      invariant(program.kind === "disclosure_v1" && program.stateKey === "evidence", "E_NARRATION_SHAPE");
      var targets = new Map();
      var targetKeys = Object.keys(scene.targets);
      invariant(plain(scene.targets) && targetKeys.length <= MAX_TARGETS, "E_TARGET_REGISTRY");
      for (var targetIndex = 0; targetIndex < targetKeys.length; targetIndex += 1) {
        var targetKey = targetKeys[targetIndex];
        nonEmptyText(targetKey, "E_TARGET_REGISTRY", 140);
        var target = exactKeys(scene.targets[targetKey], ["kind"], ["id"], "E_TARGET_REGISTRY");
        if (target.kind === "source") {
          safeId(target.id, "E_TARGET_REGISTRY");
          invariant(evidenceInfo.sourceIds.has(target.id) && targetKey === "source:" + target.id, "E_TARGET_REGISTRY");
        } else {
          invariant(!own(target, "id") && ((target.kind === "evidence" && (targetKey === "evidence:open" || targetKey === "evidence:close")) || (target.kind === "static" && targetKey === "static:toggle")), "E_TARGET_REGISTRY");
        }
        targets.set(targetKey, target);
      }
      invariant(targets.has("evidence:open") && targets.has("evidence:close") && targets.has("static:toggle"), "E_TARGET_REGISTRY");
      var expectedTargetCount = 3;
      for (var sourceIndex = 0; sourceIndex < scene.evidence.sources.length; sourceIndex += 1) {
        invariant(scene.evidence.sources[sourceIndex].linked === targets.has("source:" + scene.evidence.sources[sourceIndex].id), "E_TARGET_REGISTRY");
        if (scene.evidence.sources[sourceIndex].linked) { expectedTargetCount += 1; }
      }
      invariant(targets.size === expectedTargetCount, "E_TARGET_REGISTRY");
      boundedArray(scene.steps, 80, "E_STEP_SHAPE");
      var stepKeys = new Set();
      var gotoIds = [];
      var waitMs = 0;
      for (var stepIndex = 0; stepIndex < scene.steps.length; stepIndex += 1) {
        var stepRecord = exactKeys(scene.steps[stepIndex], ["stepKey", "action"], ["targetKey"], "E_STEP_SHAPE");
        safeId(stepRecord.stepKey, "E_STEP_SHAPE");
        invariant(!stepKeys.has(stepRecord.stepKey), "E_STEP_SHAPE");
        stepKeys.add(stepRecord.stepKey);
        var action = stepRecord.action;
        invariant(plain(action) && typeof action.type === "string", "E_STEP_SHAPE");
        if (action.type === "openEvidence" || action.type === "closeEvidence") {
          exactKeys(action, ["type"], [], "E_STEP_SHAPE");
          invariant(stepRecord.targetKey === (action.type === "openEvidence" ? "evidence:open" : "evidence:close"), "E_STEP_SHAPE");
        } else if (action.type === "goto") {
          exactKeys(action, ["type", "slideId"], [], "E_STEP_SHAPE");
          safeId(action.slideId, "E_STEP_SHAPE");
          invariant(!own(stepRecord, "targetKey"), "E_STEP_SHAPE");
          gotoIds.push(action.slideId);
        } else if (action.type === "wait") {
          exactKeys(action, ["type", "ms"], [], "E_STEP_SHAPE");
          invariant(!own(stepRecord, "targetKey"), "E_STEP_SHAPE");
          waitMs += integer(action.ms, 0, 5000, "E_STEP_SHAPE");
        } else {
          invariant(false, "E_STEP_SHAPE");
        }
      }
      invariant(waitMs <= 30000, "E_STEP_SHAPE");
      deepFreeze(scene);
      return Object.freeze({ ordinal: ordinal, type: scene.type, scene: scene, control: null, controls: new Map(), quantities: new Map(), definitions: new Map(), targets: targets, acceptedStates: modes.size, viewItems: 0, stepCount: scene.steps.length, waitMs: waitMs, gotoIds: Object.freeze(gotoIds) });
    }

    function validateTask5Control(value, scale, code) {
      invariant(plain(value), code);
      if (value.kind === "range") {
        var range = exactKeys(value, ["id", "kind", "label", "min", "max", "step", "quantity", "lineage"], [], code);
        safeId(range.id, code);
        nonEmptyText(range.label, code, 40);
        decimal(range.min, scale, code);
        decimal(range.max, scale, code);
        decimal(range.step, scale, code);
        safeId(range.quantity, code);
        validateLineage(range.lineage, code);
        var positions = DECIMAL.positions(range, scale);
        invariant(positions > BigInt(0) && positions <= BigInt(10000), code);
        var rangeValues = [];
        for (var rangeIndex = BigInt(0); rangeIndex <= positions; rangeIndex += BigInt(1)) {
          rangeValues.push(DECIMAL.canonical(DECIMAL.valueAtIndex(String(rangeIndex), range, scale), scale));
        }
        return Object.freeze({ control: range, values: Object.freeze(rangeValues) });
      }
      invariant(["segmented", "toggle", "select"].indexOf(value.kind) >= 0, code);
      var optionControl = exactKeys(value, ["id", "kind", "label", "options"], [], code);
      safeId(optionControl.id, code);
      nonEmptyText(optionControl.label, code, 40);
      var maximum = optionControl.kind === "toggle" ? 2 : optionControl.kind === "segmented" ? 4 : 8;
      boundedArray(optionControl.options, maximum, code, 2);
      invariant(optionControl.kind !== "toggle" || optionControl.options.length === 2, code);
      var values = [];
      for (var optionIndex = 0; optionIndex < optionControl.options.length; optionIndex += 1) {
        var option = exactKeys(optionControl.options[optionIndex], ["value", "label"], [], code);
        safeId(option.value, code);
        invariant(values.indexOf(option.value) < 0, code);
        nonEmptyText(option.label, code, 40);
        values.push(option.value);
      }
      return Object.freeze({ control: optionControl, values: Object.freeze(values) });
    }

    function validateTask5Definitions(scene, quantities) {
      invariant(plain(scene.outputDefinitions) && Object.keys(scene.outputDefinitions).length <= 64, "E_OUTPUT_REGISTRY");
      return registry(scene.outputDefinitions, function (definition) {
        invariant(plain(definition), "E_OUTPUT_SHAPE");
        if (definition.kind === "numeric") {
          exactKeys(definition, ["kind", "label", "quantity", "format", "round"], [], "E_OUTPUT_SHAPE");
          nonEmptyText(definition.label, "E_OUTPUT_SHAPE", 40);
          safeId(definition.quantity, "E_OUTPUT_SHAPE");
          invariant(quantities.has(definition.quantity), "E_OUTPUT_REFERENCE");
          invariant(["number", "percent", "currency", "duration", "score"].indexOf(definition.format) >= 0, "E_OUTPUT_SHAPE");
          integer(definition.round, 0, 6, "E_OUTPUT_SHAPE");
        } else {
          exactKeys(definition, ["kind", "label"], [], "E_OUTPUT_SHAPE");
          invariant(definition.kind === "text", "E_OUTPUT_SHAPE");
          nonEmptyText(definition.label, "E_OUTPUT_SHAPE", 500);
        }
      }, "E_OUTPUT_REGISTRY", outputId);
    }

    function validateTask5View(value, scale, resolved, code) {
      invariant(plain(value), code);
      if (value.component === "dot_plot") {
        var dot = validateDotView(value, scale, resolved, code);
        return Object.freeze({ component: "dot_plot", ids: dot.pointIds, xScale: dot.xScale, yScale: dot.yScale });
      }
      if (value.component === "recommendation_panel") {
        var recommendation = exactKeys(value, ["component", "score", "annotation"], [], code);
        validateTypedValue(recommendation.score, scale, code, !resolved);
        text(recommendation.annotation, code, 500);
        return Object.freeze({ component: "recommendation_panel", ids: new Set(["score"]), xScale: null, yScale: null });
      }
      invariant(value.component === "bar_compare" || value.component === "ranked_list", code);
      var required = ["component", "items"];
      var optional = [];
      if (value.component === "bar_compare" || own(value, "quantity")) {
        required = required.concat(["quantity", "domain", "baseline"]);
      } else {
        optional = ["quantity", "domain", "baseline"];
      }
      var view = exactKeys(value, required, optional, code);
      if (own(view, "quantity")) {
        safeId(view.quantity, code);
        boundedArray(view.domain, 2, code, 2);
        invariant(view.domain.length === 2, code);
        decimalAny(view.domain[0], code);
        decimalAny(view.domain[1], code);
        decimalAny(view.baseline, code);
      }
      boundedArray(view.items, 12, code, 1);
      var ids = new Set();
      var ranks = new Set();
      for (var itemIndex = 0; itemIndex < view.items.length; itemIndex += 1) {
        var item = view.items[itemIndex];
        var itemRequired = ["id", "label", "emphasis", "removed"];
        var itemOptional = [];
        if (view.component === "bar_compare") {
          itemRequired = itemRequired.concat(["value"]);
          if (resolved) { itemRequired.push("valueText"); }
        } else {
          itemRequired.push("rank");
          if (own(item, "metric")) {
            itemRequired.push("metric");
            if (resolved) { itemRequired.push("metricText"); }
          }
        }
        var row = exactKeys(item, itemRequired, itemOptional, code);
        safeId(row.id, code);
        invariant(!ids.has(row.id), code);
        ids.add(row.id);
        nonEmptyText(row.label, code, 500);
        booleanValue(row.emphasis, code);
        booleanValue(row.removed, code);
        if (view.component === "bar_compare") {
          validateTypedValue(row.value, scale, code, !resolved);
          if (resolved) { text(row.valueText, code, 500); }
        } else {
          integer(row.rank, 1, view.items.length, code);
          invariant(!ranks.has(row.rank), code);
          ranks.add(row.rank);
          if (own(row, "metric")) {
            validateTypedValue(row.metric, scale, code, !resolved);
            if (resolved) { text(row.metricText, code, 500); }
          }
        }
      }
      return Object.freeze({ component: view.component, ids: ids, xScale: null, yScale: null });
    }

    function validateTask5Model(model, scale, code) {
      invariant(plain(model) && typeof model.kind === "string", code);
      function typed(value) { validateTypedValue(value, scale, code, false); }
      function pair(value) { invariant(Array.isArray(value) && value.length === 2, code); }
      if (model.kind === "linear") {
        exactKeys(model, ["kind", "output", "intercept", "terms"], [], code);
        outputId(model.output, code);
        typed(model.intercept);
        boundedArray(model.terms, 8, code, 1);
        for (var linearIndex = 0; linearIndex < model.terms.length; linearIndex += 1) {
          pair(model.terms[linearIndex]);
          safeId(model.terms[linearIndex][0], code);
          var term = exactKeys(model.terms[linearIndex][1], ["value", "inputQuantity", "outputQuantity"], [], code);
          typed(term.value);
          safeId(term.inputQuantity, code);
          safeId(term.outputQuantity, code);
        }
      } else if (model.kind === "lookup") {
        exactKeys(model, ["kind", "output", "input", "entries"], [], code);
        outputId(model.output, code);
        safeId(model.input, code);
        boundedArray(model.entries, 10001, code, 1);
        for (var lookupIndex = 0; lookupIndex < model.entries.length; lookupIndex += 1) {
          pair(model.entries[lookupIndex]);
          decimal(model.entries[lookupIndex][0], scale, code);
          typed(model.entries[lookupIndex][1]);
        }
      } else if (model.kind === "state_map") {
        exactKeys(model, ["kind", "input", "entries"], [], code);
        safeId(model.input, code);
        boundedArray(model.entries, 8, code, 2);
        for (var stateIndex = 0; stateIndex < model.entries.length; stateIndex += 1) {
          pair(model.entries[stateIndex]);
          safeId(model.entries[stateIndex][0], code);
          safeId(model.entries[stateIndex][1], code);
        }
      } else if (model.kind === "piecewise") {
        exactKeys(model, ["kind", "input", "output", "segments"], [], code);
        safeId(model.input, code);
        outputId(model.output, code);
        boundedArray(model.segments, 16, code, 1);
        for (var segmentIndex = 0; segmentIndex < model.segments.length; segmentIndex += 1) {
          var segment = model.segments[segmentIndex];
          invariant(plain(segment), code);
          if (segment.kind === "linear") {
            exactKeys(segment, ["kind", "min", "max", "slope", "intercept"], [], code);
            var slope = exactKeys(segment.slope, ["value", "inputQuantity", "outputQuantity"], [], code);
            typed(slope.value);
            safeId(slope.inputQuantity, code);
            safeId(slope.outputQuantity, code);
            typed(segment.intercept);
          } else {
            invariant(segment.kind === "endpoints", code);
            exactKeys(segment, ["kind", "min", "max", "start", "end"], [], code);
            typed(segment.start);
            typed(segment.end);
          }
          typed(segment.min);
          typed(segment.max);
        }
      } else if (model.kind === "score_sum") {
        exactKeys(model, ["kind", "quantity", "contributions", "bands"], [], code);
        safeId(model.quantity, code);
        boundedArray(model.contributions, 8, code, 2);
        for (var contributionIndex = 0; contributionIndex < model.contributions.length; contributionIndex += 1) {
          var contribution = model.contributions[contributionIndex];
          pair(contribution);
          safeId(contribution[0], code);
          boundedArray(contribution[1], 10001, code, 1);
          for (var scoreIndex = 0; scoreIndex < contribution[1].length; scoreIndex += 1) {
            pair(contribution[1][scoreIndex]);
            invariant(typeof contribution[1][scoreIndex][0] === "string" && contribution[1][scoreIndex][0].length <= 128, code);
            typed(contribution[1][scoreIndex][1]);
          }
        }
        boundedArray(model.bands, 8, code, 1);
        for (var bandIndex = 0; bandIndex < model.bands.length; bandIndex += 1) {
          var band = exactKeys(model.bands[bandIndex], ["id", "label", "min", "max"], [], code);
          safeId(band.id, code);
          nonEmptyText(band.label, code, 40);
          typed(band.min);
          typed(band.max);
        }
      } else {
        invariant(model.kind === "operation_graph", code);
        exactKeys(model, ["kind", "nodes", "outputs"], [], code);
        boundedArray(model.nodes, 32, code, 1);
        var graphIds = new Set();
        for (var nodeIndex = 0; nodeIndex < model.nodes.length; nodeIndex += 1) {
          var node = model.nodes[nodeIndex];
          invariant(plain(node), code);
          var nodeKeys = {
            input: ["id", "op", "quantity", "control"],
            constant: ["id", "op", "quantity", "constant"],
            add: ["id", "op", "quantity", "left", "right"],
            subtract: ["id", "op", "quantity", "left", "right"],
            multiply: ["id", "op", "quantity", "left", "right"],
            divide: ["id", "op", "quantity", "left", "right"],
            min: ["id", "op", "quantity", "inputs"],
            max: ["id", "op", "quantity", "inputs"],
            abs: ["id", "op", "quantity", "input"],
            clamp: ["id", "op", "quantity", "input", "min", "max"]
          };
          invariant(own(nodeKeys, node.op), code);
          exactKeys(node, nodeKeys[node.op], [], code);
          safeId(node.id, code);
          invariant(!graphIds.has(node.id), code);
          graphIds.add(node.id);
          safeId(node.quantity, code);
          if (node.op === "constant") { typed(node.constant); }
          if (node.op === "input") { safeId(node.control, code); }
          if (node.op === "min" || node.op === "max") {
            boundedArray(node.inputs, 32, code, 1);
            for (var graphInputIndex = 0; graphInputIndex < node.inputs.length; graphInputIndex += 1) { safeId(node.inputs[graphInputIndex], code); }
          }
        }
        invariant(plain(model.outputs) && Object.keys(model.outputs).length >= 1 && Object.keys(model.outputs).length <= 4, code);
        Object.keys(model.outputs).forEach(function (key) { outputId(key, code); safeId(model.outputs[key], code); });
      }
      return model.kind;
    }

    function validateTask5Narration(value, lang, scale, code) {
      var item = exactKeys(value, ["locale", "templates", "templatesByLocale", "messages", "messagesByLocale", "program", "validatedVariants", "comparison", "maxScalars"], [], code);
      invariant(item.locale === lang && item.comparison === "initialState" && item.maxScalars === 160, code);
      integer(item.validatedVariants, 0, MAX_NODES, code);
      exactKeys(item.templatesByLocale, ["en", "ja"], [], code);
      exactKeys(item.messagesByLocale, ["en", "ja"], [], code);
      invariant(item.templates === item.templatesByLocale[lang] || JSON.stringify(item.templates) === JSON.stringify(item.templatesByLocale[lang]), code);
      invariant(item.messages === item.messagesByLocale[lang] || JSON.stringify(item.messages) === JSON.stringify(item.messagesByLocale[lang]), code);
      var program = item.program;
      invariant(plain(program) && typeof program.kind === "string", code);
      if (program.kind === "disclosure_v1") {
        exactKeys(program, ["kind", "stateKey"], [], code);
        invariant(program.stateKey === "evidence" || program.stateKey === "panel", code);
      } else if (program.kind === "state_delta_v1") {
        exactKeys(program, ["kind", "controls", "baselineView"], [], code);
        boundedArray(program.controls, 1, code, 1);
        boundedArray(program.baselineView, 12, code, 1);
        for (var baselineViewIndex = 0; baselineViewIndex < program.baselineView.length; baselineViewIndex += 1) {
          var baselineViewItem = program.baselineView[baselineViewIndex];
          var baselineViewKeys = plain(baselineViewItem) ? Object.keys(baselineViewItem).sort().join(",") : "";
          if (baselineViewKeys === ["id", "highlight", "removed", "x", "y"].sort().join(",")) {
            exactKeys(baselineViewItem, ["id", "highlight", "removed", "x", "y"], [], code);
            safeId(baselineViewItem.id, code);
            booleanValue(baselineViewItem.highlight, code);
            booleanValue(baselineViewItem.removed, code);
            decimalAny(baselineViewItem.x, code);
            decimalAny(baselineViewItem.y, code);
          } else if (baselineViewKeys === ["id", "emphasis", "removed", "value"].sort().join(",")) {
            exactKeys(baselineViewItem, ["id", "emphasis", "removed", "value"], [], code);
            safeId(baselineViewItem.id, code);
            booleanValue(baselineViewItem.emphasis, code);
            booleanValue(baselineViewItem.removed, code);
            decimalAny(baselineViewItem.value, code);
          } else if (
            baselineViewKeys === ["id", "rank", "emphasis", "removed"].sort().join(",") ||
            baselineViewKeys === ["id", "rank", "emphasis", "removed", "metric"].sort().join(",")
          ) {
            exactKeys(baselineViewItem, ["id", "rank", "emphasis", "removed"], ["metric"], code);
            safeId(baselineViewItem.id, code);
            integer(baselineViewItem.rank, 1, 12, code);
            booleanValue(baselineViewItem.emphasis, code);
            booleanValue(baselineViewItem.removed, code);
            if (own(baselineViewItem, "metric")) { decimalAny(baselineViewItem.metric, code); }
          } else {
            invariant(false, code);
          }
        }
      } else {
        invariant(program.kind === "numeric_delta_v1", code);
        exactKeys(program, ["kind", "controls", "outputs", "transitions"], [], code);
        boundedArray(program.controls, 8, code, 1);
        boundedArray(program.outputs, 4, code, 1);
        boundedArray(program.transitions, 4, code);
      }
      return program;
    }

    function validateTask5TargetsAndSteps(scene) {
      invariant(plain(scene.targets) && Object.keys(scene.targets).length <= MAX_TARGETS, "E_TARGET_REGISTRY");
      var targets = registry(scene.targets, function (target) {
        var record = exactKeys(target, ["kind"], ["id"], "E_TARGET_REGISTRY");
        invariant(["control", "source", "evidence", "static", "panel", "panelClose"].indexOf(record.kind) >= 0, "E_TARGET_REGISTRY");
        if (own(record, "id")) { safeId(record.id, "E_TARGET_REGISTRY"); }
      }, "E_TARGET_REGISTRY", function (key) { nonEmptyText(key, "E_TARGET_REGISTRY", 140); return key; });
      boundedArray(scene.steps, 80, "E_STEP_SHAPE");
      var gotoIds = [];
      var waitMs = 0;
      var stepKeys = new Set();
      for (var stepIndex = 0; stepIndex < scene.steps.length; stepIndex += 1) {
        var step = exactKeys(scene.steps[stepIndex], ["stepKey", "action"], ["targetKey"], "E_STEP_SHAPE");
        safeId(step.stepKey, "E_STEP_SHAPE");
        invariant(!stepKeys.has(step.stepKey), "E_STEP_SHAPE");
        stepKeys.add(step.stepKey);
        invariant(plain(step.action) && typeof step.action.type === "string", "E_STEP_SHAPE");
        if (step.action.type === "goto") { gotoIds.push(safeId(step.action.slideId, "E_STEP_SHAPE")); }
        if (step.action.type === "wait") { waitMs += integer(step.action.ms, 0, 5000, "E_STEP_SHAPE"); }
      }
      invariant(waitMs <= 30000, "E_STEP_SHAPE");
      return Object.freeze({ targets: targets, gotoIds: Object.freeze(gotoIds), waitMs: waitMs });
    }

    function validateTask5Scene(scene, slideId, lang, ordinal) {
      var rationaleKey = "interaction" + "Rationale";
      var disclosure = scene.type === "drilldown" || scene.type === "accordion";
      var stateToggle = scene.type === "state_toggle";
      var required = ["version", "slideId", "type", "locale", "scale", "purpose", "decisionJob", rationaleKey, "initialState", "printState", "controls", "quantities", "outputDefinitions", "evidence", "invariants", "fallback", "targets", "steps", "narration", "initialEvaluation"];
      if (disclosure) { required.push("states"); }
      if (stateToggle) { required.push("states", "model"); }
      if (scene.type === "slider_model" || scene.type === "score_model") { required = required.concat(["model", "reporting", "decisionContract", "view"]); }
      exactKeys(scene, required, [], "E_SCENE_SHAPE");
      invariant(scene.version === 1 && scene.slideId === slideId && scene.locale === lang, "E_SCENE_IDENTITY");
      invariant(["state_toggle", "slider_model", "score_model", "drilldown", "accordion"].indexOf(scene.type) >= 0, "E_SCENE_IDENTITY");
      integer(scene.scale, 0, 6, "E_SCENE_SCALE");
      nonEmptyText(scene.purpose, "E_SCENE_TEXT", 500);
      nonEmptyText(scene[rationaleKey], "E_SCENE_TEXT", 500);
      invariant(["fact", "insight", "action", "decision"].indexOf(scene.decisionJob) >= 0, "E_SCENE_TEXT");
      var evidenceInfo = validateEvidence(scene.evidence, "E_EVIDENCE_SHAPE");
      invariant(plain(scene.invariants) && Object.keys(scene.invariants).length <= 11, "E_INVARIANTS_SHAPE");
      validateTask5Fallback(scene.fallback);
      var route = validateTask5TargetsAndSteps(scene);
      validateTask5Narration(scene.narration, lang, scene.scale, "E_NARRATION_SHAPE");
      exactKeys(scene.initialEvaluation, ["outputs", "view"], disclosure || stateToggle ? [] : ["decision"], "E_INITIAL_EVALUATION");

      if (disclosure) {
        invariant(scene.controls.length === 0 && Object.keys(scene.quantities).length === 0 && Object.keys(scene.outputDefinitions).length === 0, "E_SCENE_SHAPE");
        exactKeys(scene.initialState, ["panel"], [], "E_INITIAL_STATE");
        exactKeys(scene.printState, ["panel"], [], "E_PRINT_STATE");
        invariant(scene.initialState.panel === scene.printState.panel, "E_PRINT_STATE");
        invariant(plain(scene.states) && Array.isArray(scene.states.panels), "E_PANEL_SHAPE");
        exactKeys(scene.states, scene.type === "drilldown" ? ["panels", "parentSummary", "returnLabel"] : ["panels", "allowNone"], [], "E_PANEL_SHAPE");
        boundedArray(scene.states.panels, 8, "E_PANEL_SHAPE", 1);
        var panelIds = [];
        for (var panelIndex = 0; panelIndex < scene.states.panels.length; panelIndex += 1) {
          var panel = exactKeys(scene.states.panels[panelIndex], ["id", "label", "heading", "body", "sourceRefs"], [], "E_PANEL_SHAPE");
          safeId(panel.id, "E_PANEL_SHAPE");
          invariant(panelIds.indexOf(panel.id) < 0, "E_PANEL_SHAPE");
          panelIds.push(panel.id);
          nonEmptyText(panel.label, "E_PANEL_SHAPE", 64);
          nonEmptyText(panel.heading, "E_PANEL_SHAPE", 500);
          nonEmptyText(panel.body, "E_PANEL_SHAPE", 2000);
          textArray(panel.sourceRefs, 20, "E_PANEL_SHAPE");
        }
        if (scene.type === "drilldown") {
          nonEmptyText(scene.states.parentSummary, "E_PANEL_SHAPE", 2000);
          nonEmptyText(scene.states.returnLabel, "E_PANEL_SHAPE", 500);
        } else { booleanValue(scene.states.allowNone, "E_PANEL_SHAPE"); }
        var panelAllowsNone = scene.type === "drilldown" || scene.states.allowNone;
        for (var panelStateIndex = 0; panelStateIndex < 2; panelStateIndex += 1) {
          var panelState = panelStateIndex === 0 ? scene.initialState.panel : scene.printState.panel;
          invariant((panelState === null && panelAllowsNone) || panelIds.indexOf(panelState) >= 0, "E_INITIAL_STATE");
        }
        invariant(Object.keys(scene.initialEvaluation.outputs).length === 0 && scene.initialEvaluation.view === null, "E_INITIAL_EVALUATION");
        deepFreeze(scene);
        return Object.freeze({ ordinal: ordinal, type: scene.type, scene: scene, control: null, controls: new Map(), controlList: Object.freeze([]), controlDomains: new Map(), quantities: new Map(), definitions: new Map(), targets: route.targets, acceptedStates: panelIds.length + (panelAllowsNone ? 1 : 0), viewItems: 0, stepCount: scene.steps.length, waitMs: route.waitMs, gotoIds: route.gotoIds, xScale: null, yScale: null });
      }

      boundedArray(scene.controls, 8, "E_CONTROL_SHAPE", 1);
      var controls = new Map();
      var controlDomains = new Map();
      var controlList = [];
      var acceptedStates = 1;
      for (var controlIndex = 0; controlIndex < scene.controls.length; controlIndex += 1) {
        var validated = validateTask5Control(scene.controls[controlIndex], scene.scale, "E_CONTROL_SHAPE");
        invariant(!controls.has(validated.control.id), "E_CONTROL_ID");
        controls.set(validated.control.id, validated.control);
        controlDomains.set(validated.control.id, validated.values);
        controlList.push(validated.control);
        acceptedStates *= validated.values.length;
      }
      invariant(acceptedStates <= MAX_ACCEPTED_STATES, "E_STATE_SPACE");
      invariant((scene.type !== "state_toggle" || (controlList.length === 1 && ["segmented", "select"].indexOf(controlList[0].kind) >= 0)) && (scene.type !== "slider_model" || (controlList.length === 1 && controlList[0].kind === "range")) && (scene.type !== "score_model" || (controlList.length >= 2 && controlList.length <= 8)), "E_CONTROL_SHAPE");
      for (var stateKeyIndex = 0; stateKeyIndex < 2; stateKeyIndex += 1) {
        var stateKey = stateKeyIndex === 0 ? "initialState" : "printState";
        invariant(plain(scene[stateKey]) && Object.keys(scene[stateKey]).length === controlList.length, "E_INITIAL_STATE");
        for (var stateControlIndex = 0; stateControlIndex < controlList.length; stateControlIndex += 1) {
          var stateControl = controlList[stateControlIndex];
          invariant(own(scene[stateKey], stateControl.id) && controlDomains.get(stateControl.id).indexOf(scene[stateKey][stateControl.id]) >= 0, "E_INITIAL_STATE");
        }
      }
      invariant(JSON.stringify(scene.initialState) === JSON.stringify(scene.printState), "E_PRINT_STATE");
      var quantities = registry(scene.quantities, function (quantity) { validateQuantity(quantity, "E_QUANTITY_SHAPE"); }, "E_QUANTITY_REGISTRY");
      var definitions = validateTask5Definitions(scene, quantities);
      var modelKind = validateTask5Model(scene.model, scene.scale, "E_MODEL_SHAPE");
      var allowedModels = scene.type === "state_toggle" ? ["state_map"] : scene.type === "slider_model" ? ["linear", "lookup", "piecewise", "operation_graph"] : ["score_sum"];
      invariant(allowedModels.indexOf(modelKind) >= 0, "E_MODEL_KIND");
      invariant(plain(scene.initialEvaluation.outputs) && Object.keys(scene.initialEvaluation.outputs).length === definitions.size, "E_INITIAL_OUTPUTS");
      definitions.forEach(function (definition, key) {
        invariant(own(scene.initialEvaluation.outputs, key), "E_INITIAL_OUTPUTS");
        validateTypedValue(scene.initialEvaluation.outputs[key], scene.scale, "E_INITIAL_OUTPUTS", false);
      });
      var viewInfo;
      var viewItems = 0;
      if (stateToggle) {
        boundedArray(scene.states, 8, "E_STATE_SHAPE", 2);
        var selectedView = null;
        for (var stateRowIndex = 0; stateRowIndex < scene.states.length; stateRowIndex += 1) {
          var stateRow = exactKeys(scene.states[stateRowIndex], ["id", "lineage", "view"], [], "E_STATE_SHAPE");
          safeId(stateRow.id, "E_STATE_SHAPE");
          validateLineage(stateRow.lineage, "E_STATE_SHAPE");
          var stateView = validateTask5View(stateRow.view, scene.scale, true, "E_VIEW_SHAPE");
          invariant(["bar_compare", "ranked_list", "dot_plot"].indexOf(stateView.component) >= 0, "E_VIEW_SHAPE");
          viewItems += stateView.ids.size;
          if (stateRow.id === scene.initialState[controlList[0].id]) { selectedView = stateRow.view; viewInfo = stateView; }
        }
        invariant(selectedView && JSON.stringify(selectedView) === JSON.stringify(scene.initialEvaluation.view), "E_INITIAL_VIEW");
      } else {
        viewInfo = validateTask5View(scene.view, scene.scale, false, "E_VIEW_SHAPE");
        var resolvedView = validateTask5View(scene.initialEvaluation.view, scene.scale, true, "E_INITIAL_VIEW");
        invariant(viewInfo.component === resolvedView.component, "E_INITIAL_VIEW");
        viewItems = viewInfo.ids.size + resolvedView.ids.size;
        exactKeys(scene.reporting, ["primaryOutput", "secondaryOutputs"], [], "E_REPORTING_SHAPE");
        outputId(scene.reporting.primaryOutput, "E_REPORTING_SHAPE");
        boundedArray(scene.reporting.secondaryOutputs, 3, "E_REPORTING_SHAPE");
        var decision = exactKeys(scene.decisionContract, ["id", "metric", "operator", "threshold", "whenMet", "whenNotMet"], [], "E_DECISION_SHAPE");
        safeId(decision.id, "E_DECISION_SHAPE");
        validateTypedValue(decision.metric, scene.scale, "E_DECISION_SHAPE", true);
        invariant(["gte", "gt", "lte", "lt"].indexOf(decision.operator) >= 0, "E_DECISION_SHAPE");
        exactKeys(decision.threshold, ["value", "quantity", "provenance"], [], "E_DECISION_SHAPE");
        decimal(decision.threshold.value, scene.scale, "E_DECISION_SHAPE");
        safeId(decision.threshold.quantity, "E_DECISION_SHAPE");
        validateProvenance(decision.threshold.provenance, "E_DECISION_SHAPE");
        for (var branchIndex = 0; branchIndex < 2; branchIndex += 1) {
          var branch = branchIndex === 0 ? decision.whenMet : decision.whenNotMet;
          exactKeys(branch, ["status", "recommendation"], [], "E_DECISION_SHAPE");
          nonEmptyText(branch.status, "E_DECISION_SHAPE", 32);
          nonEmptyText(branch.recommendation, "E_DECISION_SHAPE", 500);
        }
        invariant(plain(scene.initialEvaluation.decision), "E_INITIAL_DECISION");
      }
      deepFreeze(scene);
      return Object.freeze({ ordinal: ordinal, type: scene.type, scene: scene, control: controlList[0], controls: controls, controlList: Object.freeze(controlList), controlDomains: controlDomains, quantities: quantities, definitions: definitions, targets: route.targets, acceptedStates: acceptedStates, viewItems: viewItems, stepCount: scene.steps.length, waitMs: route.waitMs, gotoIds: route.gotoIds, xScale: viewInfo ? viewInfo.xScale : null, yScale: viewInfo ? viewInfo.yScale : null });
    }

    function validateScene(scene, slideId, lang, ordinal) {
      if (plain(scene) && scene.type === "evidence_only") {
        return validateEvidenceScene(scene, slideId, lang, ordinal);
      }
      if (plain(scene) && scene.type === "slider_model" && plain(scene.model) && scene.model.kind === "linear" && plain(scene.view) && scene.view.component === "dot_plot") {
        return validateTask4Scene(scene, slideId, lang, ordinal);
      }
      if (plain(scene) && ["state_toggle", "slider_model", "score_model", "drilldown", "accordion"].indexOf(scene.type) >= 0) {
        return validateTask5Scene(scene, slideId, lang, ordinal);
      }
      return validateTask4Scene(scene, slideId, lang, ordinal);
    }

    function validateDisplay(display, runtime, section) {
      exactKeys(display, ["staticSummary", "baselineAnnotation", "thresholdText", "axisTickLabels"], [], "E_DISPLAY_SHAPE");
      text(display.baselineAnnotation, "E_DISPLAY_TEXT", 2000);
      if (display.thresholdText !== null) { text(display.thresholdText, "E_DISPLAY_TEXT", 500); }
      var ticks = display.axisTickLabels;
      if (ticks !== null) {
        exactKeys(ticks, ["x", "y"], [], "E_DISPLAY_TICKS");
        for (var axisIndex = 0; axisIndex < 2; axisIndex += 1) {
          var axis = axisIndex === 0 ? "x" : "y";
          invariant(Array.isArray(ticks[axis]) && ticks[axis].length === 2, "E_DISPLAY_TICKS");
          text(ticks[axis][0], "E_DISPLAY_TEXT", 500);
          text(ticks[axis][1], "E_DISPLAY_TEXT", 500);
        }
      }
      var summary = exactKeys(display.staticSummary, ["headline", "source", "paragraphs", "values", "decision"], [], "E_DISPLAY_SUMMARY");
      text(summary.headline, "E_DISPLAY_TEXT", 500);
      text(summary.source, "E_DISPLAY_TEXT", 500);
      invariant(Array.isArray(summary.paragraphs), "E_DISPLAY_SUMMARY");
      var paragraphNodes = section.querySelectorAll(".scene-summary [data-summary-paragraph]");
      invariant(paragraphNodes.length === summary.paragraphs.length, "E_DISPLAY_DRIFT");
      for (var paragraphIndex = 0; paragraphIndex < summary.paragraphs.length; paragraphIndex += 1) {
        text(summary.paragraphs[paragraphIndex], "E_DISPLAY_TEXT", 2000);
        invariant(paragraphNodes[paragraphIndex].textContent === summary.paragraphs[paragraphIndex], "E_DISPLAY_DRIFT");
      }
      var heading = section.querySelector("h1");
      var source = section.querySelector(".semantic-source");
      invariant(heading && heading.textContent === summary.headline && source && source.textContent === summary.source, "E_DISPLAY_DRIFT");
      var scene = runtime.scene;
      if (own(scene.fallback, "paragraphs")) {
        invariant(JSON.stringify(summary.paragraphs) === JSON.stringify(scene.fallback.paragraphs), "E_DISPLAY_DRIFT");
        invariant(display.baselineAnnotation === scene.fallback.baselineAnnotation, "E_DISPLAY_DRIFT");
        invariant(display.thresholdText === scene.fallback.thresholdText, "E_DISPLAY_DRIFT");
        invariant(JSON.stringify(display.axisTickLabels) === JSON.stringify(scene.fallback.axisTickLabels), "E_DISPLAY_DRIFT");
      }
      if (scene.type === "evidence_only" || scene.type === "drilldown" || scene.type === "accordion") {
        invariant(display.thresholdText === null && display.axisTickLabels === null && Array.isArray(summary.values) && summary.values.length === 0 && summary.decision === null, "E_DISPLAY_DRIFT");
        return;
      }
      if (scene.type === "state_toggle") {
        invariant(display.thresholdText === null && Array.isArray(summary.values) && summary.values.length === 0 && summary.decision === null, "E_DISPLAY_DRIFT");
        return;
      }
      var outputIds = [scene.reporting.primaryOutput].concat(scene.reporting.secondaryOutputs);
      if (scene.type === "score_model") {
        outputIds.push("classification");
      }
      invariant(Array.isArray(summary.values) && summary.values.length === outputIds.length, "E_DISPLAY_VALUES");
      for (var outputIndex = 0; outputIndex < outputIds.length; outputIndex += 1) {
        var outputId = outputIds[outputIndex];
        var item = exactKeys(summary.values[outputIndex], ["id", "label", "text"], [], "E_DISPLAY_VALUES");
        var definition = runtime.definitions.get(outputId);
        var output = scene.initialEvaluation.outputs[outputId];
        invariant(item.id === outputId && item.label === definition.label, "E_DISPLAY_DRIFT");
        if (definition.kind === "numeric") {
          var quantity = runtime.quantities.get(definition.quantity);
          invariant(output.kind === "numeric" && item.text === DECIMAL.format(DECIMAL.parse(output.value, scene.scale), scene.scale, quantity.display, definition.round, false), "E_DISPLAY_DRIFT");
        } else {
          invariant(output.kind === "text" && item.text === output.value, "E_DISPLAY_DRIFT");
        }
      }
      var decision = exactKeys(summary.decision, ["status", "recommendation"], [], "E_DISPLAY_DECISION");
      invariant(decision.status === scene.initialEvaluation.decision.status && decision.recommendation === scene.initialEvaluation.decision.recommendation, "E_DISPLAY_DRIFT");
    }

    function validateStateSpace(runtime) {
      if (runtime.scene.type === "evidence_only") {
        invariant(runtime.acceptedStates >= 2 && runtime.acceptedStates <= 4, "E_STATE_SPACE");
        return;
      }
      if (runtime.scene.type === "drilldown" || runtime.scene.type === "accordion") {
        var allowsEmptyPanel = runtime.scene.type === "drilldown" || runtime.scene.states.allowNone;
        invariant(runtime.acceptedStates === runtime.scene.states.panels.length + (allowsEmptyPanel ? 1 : 0), "E_STATE_SPACE");
        return;
      }
      if (!runtime.controlList) {
        var legacyControl = runtime.control;
        for (var legacyIndex = BigInt(0); legacyIndex < BigInt(runtime.acceptedStates); legacyIndex += BigInt(1)) {
          var legacyInputs = new Map();
          legacyInputs.set(legacyControl.id, DECIMAL.valueAtIndex(String(legacyIndex), legacyControl, runtime.scene.scale));
          var legacyEvaluation = MODEL.evaluate(runtime, legacyInputs, "direct", legacyControl.id);
          invariant(legacyEvaluation.decision.outcome === "met" || legacyEvaluation.decision.outcome === "notMet", "E_STATE_SPACE");
          invariant(scalarLength(legacyEvaluation.narration, "E_STATE_SPACE") <= runtime.scene.narration.maxScalars, "E_STATE_SPACE");
        }
        return;
      }
      for (var stateIndex = 0; stateIndex < runtime.acceptedStates; stateIndex += 1) {
        var cursor = stateIndex;
        var inputs = new Map();
        for (var controlIndex = runtime.controlList.length - 1; controlIndex >= 0; controlIndex -= 1) {
          var control = runtime.controlList[controlIndex];
          var domain = runtime.controlDomains.get(control.id);
          var selected = domain[cursor % domain.length];
          cursor = Math.floor(cursor / domain.length);
          inputs.set(control.id, control.kind === "range" ? DECIMAL.parse(selected, runtime.scene.scale) : selected);
        }
        var evaluation = MODEL.evaluate(runtime, inputs, "restore", null);
        if (runtime.scene.decisionContract) {
          invariant(evaluation.decision.outcome === "met" || evaluation.decision.outcome === "notMet", "E_STATE_SPACE");
        } else {
          invariant(evaluation.decision === null, "E_STATE_SPACE");
        }
        invariant(scalarLength(evaluation.narration, "E_STATE_SPACE") <= runtime.scene.narration.maxScalars, "E_STATE_SPACE");
      }
    }

    function load() {
      var payload = decode();
      exactKeys(payload, ["version", "kind", "lang", "locale", "slides"], [], "E_ENVELOPE_SHAPE");
      invariant(payload.version === 1 && payload.kind === "interactive-deck", "E_ENVELOPE_VERSION");
      invariant((payload.lang === "en" && payload.locale === "en-US") || (payload.lang === "ja" && payload.locale === "ja-JP"), "E_ENVELOPE_LOCALE");
      invariant(Array.isArray(payload.slides) && payload.slides.length >= 1 && payload.slides.length <= 64, "E_SLIDE_COUNT");
      var sections = document.querySelectorAll("#idrt-deck-pages > .slide");
      invariant(sections.length === payload.slides.length, "E_SLIDE_COUNT");
      var slides = [];
      var ids = new Set();
      var acceptedStates = 0;
      var viewItems = 0;
      var targetCount = 0;
      var stepCount = 0;
      var waitMs = DEFAULT_PAGE_PAUSE_MS * payload.slides.length;
      for (var index = 0; index < payload.slides.length; index += 1) {
        var record = exactKeys(payload.slides[index], ["slideId", "scene", "display"], [], "E_SLIDE_SHAPE");
        safeId(record.slideId, "E_SLIDE_ID");
        invariant(!ids.has(record.slideId) && sections[index].getAttribute("data-slide-id") === record.slideId, "E_SLIDE_ID");
        ids.add(record.slideId);
        var runtime = null;
        if (record.scene !== null) {
          invariant(plain(record.display), "E_DISPLAY_SHAPE");
          runtime = validateScene(record.scene, record.slideId, payload.lang, index + 1);
          validateDisplay(record.display, runtime, sections[index]);
          acceptedStates += runtime.acceptedStates;
          viewItems += runtime.viewItems;
          targetCount += runtime.targets.size;
          stepCount += runtime.stepCount;
          waitMs += runtime.waitMs;
        } else {
          invariant(record.display === null, "E_DISPLAY_SHAPE");
        }
        slides.push(Object.freeze({ ordinal: index + 1, id: record.slideId, record: record, runtime: runtime }));
      }
      invariant(acceptedStates <= MAX_ACCEPTED_STATES && viewItems <= MAX_VIEW_ITEMS && targetCount <= MAX_TARGETS && stepCount <= MAX_STEPS && waitMs <= MAX_DECK_WAIT_MS, "E_DECK_BUDGET");
      for (var referenceIndex = 0; referenceIndex < slides.length; referenceIndex += 1) {
        if (slides[referenceIndex].runtime) {
          var gotoIds = slides[referenceIndex].runtime.gotoIds;
          for (var gotoIndex = 0; gotoIndex < gotoIds.length; gotoIndex += 1) {
            invariant(ids.has(gotoIds[gotoIndex]), "E_STEP_REFERENCE");
          }
          validateStateSpace(slides[referenceIndex].runtime);
        }
      }
      deepFreeze(payload);
      return Object.freeze({ payload: payload, slides: Object.freeze(slides) });
    }
    return Object.freeze({ load: load });
  }());

  var MODEL = (function () {
    function decide(scene, output) {
      var contract = scene.decisionContract;
      var threshold = DECIMAL.parse(contract.threshold.value, scene.scale);
      var met = contract.operator === "gte" ? output >= threshold : contract.operator === "gt" ? output > threshold : contract.operator === "lte" ? output <= threshold : output < threshold;
      var selected = met ? contract.whenMet : contract.whenNotMet;
      return Object.freeze({ outcome: met ? "met" : "notMet", distance: output - threshold, status: selected.status, recommendation: selected.recommendation });
    }

    function canonicalInput(runtime, control, value) {
      return control.kind === "range" ? DECIMAL.canonical(value, runtime.scene.scale) : value;
    }

    function optionLabel(control, value) {
      for (var optionIndex = 0; optionIndex < control.options.length; optionIndex += 1) {
        if (control.options[optionIndex].value === value) {
          return control.options[optionIndex].label;
        }
      }
      invariant(false, "E_MODEL_INPUT");
    }

    function narration(runtime, inputs, outputs, result, eventName, controlId, view) {
      var scene = runtime.scene;
      if (eventName === "initial" || eventName === "reset") {
        return scene.narration.messages[eventName];
      }
      var program = scene.narration.program;
      if (program.kind === "disclosure_v1") {
        var disclosureValue = inputs.get(program.stateKey);
        var disclosureKey = program.stateKey === "evidence" ? "evidence:" + disclosureValue : disclosureValue === null ? "panels:closed" : "openPanel:" + disclosureValue;
        return scene.narration.messages[disclosureKey] || scene.narration.messages["panels:closed"];
      }
      if (program.kind === "state_delta_v1") {
        var descriptor = program.controls[0];
        var baselineById = new Map();
        for (var baselineIndex = 0; baselineIndex < program.baselineView.length; baselineIndex += 1) {
          baselineById.set(program.baselineView[baselineIndex].id, program.baselineView[baselineIndex]);
        }
        var collection = view.component === "dot_plot" ? view.points : view.items;
        var moved = 0;
        var changed = 0;
        var removed = 0;
        for (var viewIndex = 0; viewIndex < collection.length; viewIndex += 1) {
          var current = collection[viewIndex];
          var baseline = baselineById.get(current.id);
          invariant(baseline, "E_NARRATION_VIEW");
          if ((own(current, "rank") && current.rank !== baseline.rank) || (own(current, "x") && current.x.value !== baseline.x) || (own(current, "y") && current.y.value !== baseline.y)) { moved += 1; }
          if ((baseline.removed && !current.removed) || (own(current, "value") && current.value.value !== baseline.value) || (own(current, "metric") && current.metric.value !== baseline.metric) || current.emphasis !== baseline.emphasis || current.highlight !== baseline.highlight) { changed += 1; }
          if (current.removed && !baseline.removed) { removed += 1; }
        }
        var stateSentence = scene.narration.templates.state
          .replace("{label}", descriptor.label)
          .replace("{option}", optionLabel(descriptor, inputs.get(descriptor.id)))
          .replace("{moved}", String(moved))
          .replace("{changed}", String(changed))
          .replace("{removed}", String(removed));
        invariant(scalarLength(stateSentence, "E_NARRATION_LENGTH") <= scene.narration.maxScalars, "E_NARRATION_LENGTH");
        return stateSentence;
      }
      var changedControls = [];
      for (var index = 0; index < program.controls.length; index += 1) {
        var atom = program.controls[index];
        if (canonicalInput(runtime, runtime.controls.get(atom.id), inputs.get(atom.id)) !== atom.baseline) {
          changedControls.push(atom);
        }
      }
      if (!changedControls.length) {
        return scene.narration.messages.initial;
      }
      var activeDescriptor = null;
      for (var controlIndex = 0; controlIndex < program.controls.length; controlIndex += 1) {
        if (program.controls[controlIndex].id === controlId) {
          activeDescriptor = program.controls[controlIndex];
        }
      }
      var prefix;
      if (eventName === "restore" && changedControls.length > 1) {
        prefix = scene.narration.templates.restore.replace("{count}", String(changedControls.length));
      } else {
        activeDescriptor = eventName === "restore" ? changedControls[0] : activeDescriptor;
        invariant(activeDescriptor, "E_NARRATION_CONTROL");
        var activeControl = runtime.controls.get(activeDescriptor.id);
        if (activeControl.kind === "range") {
          var inputDelta = inputs.get(activeDescriptor.id) - DECIMAL.parse(activeDescriptor.baseline, scene.scale);
          prefix = activeDescriptor.label + " " + DECIMAL.format(inputDelta, scene.scale, activeDescriptor.display, activeDescriptor.precision, true);
        } else {
          prefix = activeDescriptor.label + ": " + optionLabel(activeDescriptor, inputs.get(activeDescriptor.id));
        }
      }
      var parts = [prefix];
      for (var outputIndex = 0; outputIndex < program.outputs.length; outputIndex += 1) {
        var outputAtom = program.outputs[outputIndex];
        var outputDelta = outputs.get(outputAtom.id) - DECIMAL.parse(outputAtom.baseline, scene.scale);
        if (outputDelta !== BigInt(0)) {
          parts.push(outputAtom.label + " " + DECIMAL.format(outputDelta, scene.scale, outputAtom.display, outputAtom.precision, true));
        }
      }
      for (var transitionIndex = 0; transitionIndex < program.transitions.length; transitionIndex += 1) {
        var transition = program.transitions[transitionIndex];
        var after = outputs.get(transition.id);
        if (after && after !== transition.baseline) {
          parts.push(transition.baseline + " → " + after);
        }
      }
      while (parts.join("; ").length > scene.narration.maxScalars && parts.length > 2) {
        parts.splice(parts.length - 2, 1);
      }
      var sentence = parts.join("; ");
      invariant(scalarLength(sentence, "E_NARRATION_LENGTH") <= scene.narration.maxScalars, "E_NARRATION_LENGTH");
      return sentence;
    }

    function evaluateModel(runtime, inputs) {
      var scene = runtime.scene;
      var model = scene.model;
      var outputs = new Map();
      var scaleUnit = DECIMAL.power(scene.scale);
      function numeric(value) { return DECIMAL.parse(value.value, scene.scale); }
      if (model.kind === "state_map") {
        return outputs;
      }
      if (model.kind === "linear") {
        var linear = numeric(model.intercept);
        for (var termIndex = 0; termIndex < model.terms.length; termIndex += 1) {
          var term = model.terms[termIndex];
          linear += DECIMAL.roundDiv(inputs.get(term[0]) * numeric(term[1].value), scaleUnit);
        }
        outputs.set(model.output, linear);
      } else if (model.kind === "lookup") {
        var lookupKey = DECIMAL.canonical(inputs.get(model.input), scene.scale);
        for (var lookupIndex = 0; lookupIndex < model.entries.length; lookupIndex += 1) {
          if (model.entries[lookupIndex][0] === lookupKey) {
            outputs.set(model.output, numeric(model.entries[lookupIndex][1]));
          }
        }
        invariant(outputs.has(model.output), "E_MODEL_INPUT");
      } else if (model.kind === "piecewise") {
        var piecewiseInput = inputs.get(model.input);
        for (var segmentIndex = 0; segmentIndex < model.segments.length; segmentIndex += 1) {
          var segment = model.segments[segmentIndex];
          var segmentMin = numeric(segment.min);
          var segmentMax = numeric(segment.max);
          if (piecewiseInput >= segmentMin && (piecewiseInput < segmentMax || segmentIndex === model.segments.length - 1)) {
            if (segment.kind === "linear") {
              outputs.set(model.output, numeric(segment.intercept) + DECIMAL.roundDiv(piecewiseInput * numeric(segment.slope.value), scaleUnit));
            } else {
              outputs.set(model.output, numeric(segment.start) + DECIMAL.roundDiv((numeric(segment.end) - numeric(segment.start)) * (piecewiseInput - segmentMin), segmentMax - segmentMin));
            }
            break;
          }
        }
        invariant(outputs.has(model.output), "E_MODEL_INPUT");
      } else if (model.kind === "score_sum") {
        var total = BigInt(0);
        for (var contributionIndex = 0; contributionIndex < model.contributions.length; contributionIndex += 1) {
          var contribution = model.contributions[contributionIndex];
          var contributionControl = runtime.controls.get(contribution[0]);
          var selector = canonicalInput(runtime, contributionControl, inputs.get(contribution[0]));
          var found = false;
          for (var scoreIndex = 0; scoreIndex < contribution[1].length; scoreIndex += 1) {
            if (contribution[1][scoreIndex][0] === selector) {
              total += numeric(contribution[1][scoreIndex][1]);
              found = true;
            }
          }
          invariant(found, "E_MODEL_INPUT");
        }
        outputs.set("score", total);
        for (var bandIndex = 0; bandIndex < model.bands.length; bandIndex += 1) {
          var band = model.bands[bandIndex];
          var bandMin = numeric(band.min);
          var bandMax = numeric(band.max);
          if (total >= bandMin && (total < bandMax || bandIndex === model.bands.length - 1)) {
            outputs.set("classification", band.label);
            break;
          }
        }
        invariant(outputs.has("classification"), "E_MODEL_INPUT");
      } else {
        invariant(model.kind === "operation_graph", "E_MODEL_KIND");
        var graph = new Map();
        for (var nodeIndex = 0; nodeIndex < model.nodes.length; nodeIndex += 1) {
          var node = model.nodes[nodeIndex];
          var graphValue;
          if (node.op === "input") { graphValue = inputs.get(node.control); }
          else if (node.op === "constant") { graphValue = numeric(node.constant); }
          else if (node.op === "add") { graphValue = graph.get(node.left) + graph.get(node.right); }
          else if (node.op === "subtract") { graphValue = graph.get(node.left) - graph.get(node.right); }
          else if (node.op === "multiply") { graphValue = DECIMAL.roundDiv(graph.get(node.left) * graph.get(node.right), scaleUnit); }
          else if (node.op === "divide") { graphValue = DECIMAL.roundDiv(graph.get(node.left) * scaleUnit, graph.get(node.right)); }
          else if (node.op === "abs") { graphValue = graph.get(node.input) < BigInt(0) ? -graph.get(node.input) : graph.get(node.input); }
          else if (node.op === "clamp") { graphValue = graph.get(node.input) < graph.get(node.min) ? graph.get(node.min) : graph.get(node.input) > graph.get(node.max) ? graph.get(node.max) : graph.get(node.input); }
          else {
            var candidates = node.inputs.map(function (id) { return graph.get(id); });
            graphValue = candidates[0];
            for (var candidateIndex = 1; candidateIndex < candidates.length; candidateIndex += 1) {
              if ((node.op === "min" && candidates[candidateIndex] < graphValue) || (node.op === "max" && candidates[candidateIndex] > graphValue)) { graphValue = candidates[candidateIndex]; }
            }
          }
          invariant(typeof graphValue === "bigint", "E_MODEL_GRAPH");
          graph.set(node.id, graphValue);
        }
        Object.keys(model.outputs).forEach(function (outputId) { outputs.set(outputId, graph.get(model.outputs[outputId])); });
      }
      outputs.forEach(function (value) {
        if (typeof value === "bigint") { invariant(value <= DECIMAL.power(12 + scene.scale) && value >= -DECIMAL.power(12 + scene.scale), "E_MODEL_BOUND"); }
      });
      return outputs;
    }

    function evaluateDecision(runtime, inputs, outputs) {
      var scene = runtime.scene;
      if (!scene.decisionContract) { return null; }
      var reference = scene.decisionContract.metric.ref.split(":");
      var metric = reference[0] === "control" ? inputs.get(reference[1]) : outputs.get(reference[1]);
      invariant(typeof metric === "bigint", "E_DECISION_REFERENCE");
      var result = decide(scene, metric);
      outputs.set("decisionStatus", result.status);
      outputs.set("recommendation", result.recommendation);
      return result;
    }

    function decimalPrecision(value) {
      var marker = value.indexOf(".");
      return marker < 0 ? 0 : value.length - marker - 1;
    }

    function formatResolved(runtime, quantityId, value, precision) {
      var quantity = runtime.quantities.get(quantityId);
      invariant(quantity, "E_VIEW_REFERENCE");
      return DECIMAL.format(value, runtime.scene.scale, quantity.display, precision, false);
    }

    function resolveNumericSlot(runtime, inputs, outputs, slot) {
      if (own(slot, "ref")) {
        var reference = slot.ref.split(":");
        var value = reference[0] === "control" ? inputs.get(reference[1]) : outputs.get(reference[1]);
        invariant(typeof value === "bigint", "E_VIEW_REFERENCE");
        return Object.freeze({ value: value, reference: reference });
      }
      return Object.freeze({ value: DECIMAL.parse(slot.value, runtime.scene.scale), reference: null });
    }

    function initialResolvedViewRow(scene, component, id) {
      var initialView = scene.initialEvaluation.view;
      invariant(initialView && initialView.component === component, "E_INITIAL_VIEW");
      var collection = component === "dot_plot" ? initialView.points : initialView.items;
      for (var rowIndex = 0; rowIndex < collection.length; rowIndex += 1) {
        if (collection[rowIndex].id === id) { return collection[rowIndex]; }
      }
      invariant(false, "E_INITIAL_VIEW");
    }

    function resolveView(runtime, inputs, outputs) {
      var scene = runtime.scene;
      if (scene.type === "state_toggle") {
        var stateId = null;
        var selected = inputs.get(scene.model.input);
        for (var entryIndex = 0; entryIndex < scene.model.entries.length; entryIndex += 1) {
          if (scene.model.entries[entryIndex][0] === selected) { stateId = scene.model.entries[entryIndex][1]; }
        }
        for (var stateIndex = 0; stateIndex < scene.states.length; stateIndex += 1) {
          if (scene.states[stateIndex].id === stateId) { return scene.states[stateIndex].view; }
        }
        invariant(false, "E_VIEW_REFERENCE");
      }
      var authored = scene.view;
      if (authored.component === "recommendation_panel") {
        var scoreSlot = resolveNumericSlot(runtime, inputs, outputs, authored.score);
        var scoreDefinition = runtime.definitions.get("score");
        return Object.freeze({ component: authored.component, score: Object.freeze({ value: scoreSlot.value }), scoreText: formatResolved(runtime, scoreDefinition.quantity, scoreSlot.value, scoreDefinition.round), annotation: authored.annotation });
      }
      var key = authored.component === "dot_plot" ? "points" : "items";
      var resolvedRows = [];
      for (var rowIndex = 0; rowIndex < authored[key].length; rowIndex += 1) {
        var source = authored[key][rowIndex];
        var initialRow = initialResolvedViewRow(scene, authored.component, source.id);
        var row = { id: source.id, label: source.label, removed: source.removed };
        if (own(source, "emphasis")) { row.emphasis = source.emphasis; }
        if (own(source, "highlight")) { row.highlight = source.highlight; }
        if (own(source, "rank")) { row.rank = source.rank; }
        var slots = authored.component === "dot_plot" ? ["x", "y"] : authored.component === "bar_compare" ? ["value"] : own(source, "metric") ? ["metric"] : [];
        for (var slotIndex = 0; slotIndex < slots.length; slotIndex += 1) {
          var slotName = slots[slotIndex];
          var resolved = resolveNumericSlot(runtime, inputs, outputs, source[slotName]);
          var quantityId = authored.component === "dot_plot" ? authored[slotName + "Quantity"] : authored.quantity;
          var precision = decimalPrecision(DECIMAL.canonical(resolved.value, scene.scale));
          if (resolved.reference && resolved.reference[0] === "output") { precision = runtime.definitions.get(resolved.reference[1]).round; }
          row[slotName] = Object.freeze({ value: DECIMAL.canonical(resolved.value, scene.scale), quantity: quantityId });
          row[slotName + "Value"] = resolved.value;
          if (resolved.reference) {
            row[slotName + "Text"] = formatResolved(runtime, quantityId, resolved.value, precision);
          } else {
            invariant(typeof initialRow[slotName + "Text"] === "string", "E_INITIAL_VIEW");
            row[slotName + "Text"] = initialRow[slotName + "Text"];
          }
        }
        resolvedRows.push(Object.freeze(row));
      }
      var result = { component: authored.component };
      Object.keys(authored).forEach(function (keyName) { if (keyName !== key) { result[keyName] = authored[keyName]; } });
      result[key] = Object.freeze(resolvedRows);
      return Object.freeze(result);
    }

    function geometry(runtime, view) {
      if (!view || view.component !== "dot_plot") { return Object.freeze([]); }
      var points = [];
      var xMinimum = DECIMAL.parse(view.xDomain[0], runtime.xScale);
      var xMaximum = DECIMAL.parse(view.xDomain[1], runtime.xScale);
      var yMinimum = DECIMAL.parse(view.yDomain[0], runtime.yScale);
      var yMaximum = DECIMAL.parse(view.yDomain[1], runtime.yScale);
      for (var pointIndex = 0; pointIndex < view.points.length; pointIndex += 1) {
        var point = view.points[pointIndex];
        var xValue = own(point, "xValue") ? point.xValue : DECIMAL.parse(point.x.value, runtime.scene.scale);
        var yValue = own(point, "yValue") ? point.yValue : DECIMAL.parse(point.y.value, runtime.scene.scale);
        var scaledX = DECIMAL.rescale(xValue, runtime.scene.scale, runtime.xScale);
        var scaledY = DECIMAL.rescale(yValue, runtime.scene.scale, runtime.yScale);
        invariant(scaledX >= xMinimum && scaledX <= xMaximum && scaledY >= yMinimum && scaledY <= yMaximum, "E_VIEW_DOMAIN");
        points.push(Object.freeze({ id: point.id, x: 130 + 690 * DECIMAL.fraction(scaledX, xMinimum, xMaximum), y: 560 - 330 * DECIMAL.fraction(scaledY, yMinimum, yMaximum), xValue: xValue, yValue: yValue }));
      }
      return Object.freeze(points);
    }

    function evaluate(runtime, inputs, eventName, controlId) {
      var scene = runtime.scene;
      if (scene.type === "evidence_only" || scene.type === "drilldown" || scene.type === "accordion") {
        var stateKey = scene.type === "evidence_only" ? "evidence" : "panel";
        var message = eventName === "reset" ? scene.narration.messages.reset : narration(runtime, inputs, new Map(), null, eventName, controlId, null);
        return Object.freeze({ outputs: new Map(), outputTexts: new Map(), decision: null, points: Object.freeze([]), view: null, narration: message, stateKey: stateKey });
      }
      var outputs = evaluateModel(runtime, inputs);
      var decision = evaluateDecision(runtime, inputs, outputs);
      var outputTexts = new Map();
      outputs.forEach(function (value, outputId) {
        var definition = runtime.definitions.get(outputId);
        if (definition && definition.kind === "numeric") {
          outputTexts.set(outputId, formatResolved(runtime, definition.quantity, value, definition.round));
        } else if (typeof value === "string") {
          outputTexts.set(outputId, value);
        }
      });
      var view = resolveView(runtime, inputs, outputs);
      var points = geometry(runtime, view);
      return Object.freeze({ outputs: outputs, outputTexts: outputTexts, decision: decision, points: points, view: view, narration: narration(runtime, inputs, outputs, decision, eventName, controlId, view) });
    }

    function matchesInitial(runtime, evaluation) {
      var scene = runtime.scene;
      var expected = scene.initialEvaluation;
      if (scene.type === "evidence_only" || scene.type === "drilldown" || scene.type === "accordion") {
        invariant(evaluation.outputs.size === 0 && evaluation.decision === null && evaluation.points.length === 0 && expected.view === null, "E_INITIAL_DRIFT");
        return;
      }
      runtime.definitions.forEach(function (definition, outputId) {
        var actual = evaluation.outputs.get(outputId);
        var expectedOutput = expected.outputs[outputId];
        invariant(expectedOutput && expectedOutput.kind === definition.kind, "E_INITIAL_DRIFT");
        if (definition.kind === "numeric") { invariant(DECIMAL.canonical(actual, scene.scale) === expectedOutput.value, "E_INITIAL_DRIFT"); }
        else { invariant(actual === expectedOutput.value, "E_INITIAL_DRIFT"); }
      });
      if (expected.decision) {
        invariant(evaluation.decision && evaluation.decision.outcome === expected.decision.outcome && DECIMAL.canonical(evaluation.decision.distance, scene.scale) === expected.decision.distance && evaluation.decision.status === expected.decision.status && evaluation.decision.recommendation === expected.decision.recommendation, "E_INITIAL_DRIFT");
      }
      invariant(evaluation.view && evaluation.view.component === expected.view.component, "E_INITIAL_DRIFT");
      if (expected.view.component === "dot_plot") {
        invariant(evaluation.points.length === expected.view.points.length, "E_INITIAL_DRIFT");
        for (var pointIndex = 0; pointIndex < evaluation.points.length; pointIndex += 1) {
          invariant(evaluation.points[pointIndex].id === expected.view.points[pointIndex].id && DECIMAL.canonical(evaluation.points[pointIndex].xValue, scene.scale) === expected.view.points[pointIndex].x.value && DECIMAL.canonical(evaluation.points[pointIndex].yValue, scene.scale) === expected.view.points[pointIndex].y.value, "E_INITIAL_DRIFT");
        }
      }
    }
    return Object.freeze({ evaluate: evaluate, matchesInitial: matchesInitial });
  }());

  var STATE = (function () {
    function pageWith(page, inputs, evaluation, viewMode, failed) {
      return Object.freeze({ inputs: inputs === null ? page.inputs : inputs, evaluation: evaluation === null ? page.evaluation : evaluation, viewMode: viewMode === null ? page.viewMode : viewMode, failed: failed === null ? page.failed : failed });
    }
    function overlays(value) {
      return Object.freeze(value.slice());
    }
    function result(state, pages, nextOverlays, currentIndex, reducedMotion) {
      return Object.freeze({
        currentIndex: currentIndex === null ? state.currentIndex : currentIndex,
        pages: pages,
        overlays: overlays(nextOverlays),
        reducedMotion: reducedMotion === null ? state.reducedMotion : reducedMotion
      });
    }
    function top(state) {
      return state.overlays.length ? state.overlays[state.overlays.length - 1] : null;
    }
    function reduce(state, action, deck) {
      invariant(plain(action) && typeof action.type === "string", "E_ACTION");
      var pages = new Map(state.pages);
      if (action.type === "NAVIGATE") {
        invariant(Number.isInteger(action.index), "E_ACTION");
        return result(state, pages, [], Math.max(0, Math.min(deck.slides.length - 1, action.index)), null);
      }
      if (action.type === "SET_REDUCED_MOTION") {
        return result(state, pages, state.overlays, null, action.value === true);
      }
      if (action.type === "OPEN_PRESENTER_OVERLAY") {
        invariant(action.kind === "overview" || action.kind === "help", "E_ACTION_OVERLAY");
        var presenterOverlays = state.overlays.slice();
        var currentTop = top(state);
        if (!currentTop || currentTop.kind !== action.kind) {
          presenterOverlays.push(Object.freeze({ kind: action.kind }));
        }
        return result(state, pages, presenterOverlays, null, null);
      }
      if (action.type === "CLEAR_OVERLAYS") {
        return result(state, pages, [], null, null);
      }
      if (action.type === "CLOSE_TOP_OVERLAY") {
        var closing = top(state);
        if (!closing) {
          return result(state, pages, state.overlays, null, null);
        }
        var closingSlide = deck.slides[state.currentIndex];
        var closingPage = pages.get(closingSlide.id);
        if (closing.kind === "evidence" && closingSlide.runtime && closingSlide.runtime.scene.type === "evidence_only" && closingPage && !closingPage.failed) {
          var closingInputs = new Map(closingPage.inputs);
          closingInputs.set("evidence", "closed");
          pages.set(closingSlide.id, pageWith(closingPage, closingInputs, MODEL.evaluate(closingSlide.runtime, closingInputs, "direct", "evidence"), null, null));
        }
        return result(state, pages, state.overlays.slice(0, -1), null, null);
      }
      var slide = deck.slides[state.currentIndex];
      var page = pages.get(slide.id);
      invariant(slide.runtime && page && !page.failed, "E_ACTION_SCENE");
      if (action.type === "SET_CONTROL") {
        var selectedControl = slide.runtime.controls.get(action.id);
        invariant(selectedControl, "E_ACTION_CONTROL");
        var inputs = new Map(page.inputs);
        if (selectedControl.kind === "range") {
          inputs.set(action.id, DECIMAL.valueAtIndex(action.raw, selectedControl, slide.runtime.scene.scale));
        } else {
          invariant(slide.runtime.controlDomains.get(action.id).indexOf(action.raw) >= 0, "E_ACTION_CONTROL");
          inputs.set(action.id, action.raw);
        }
        pages.set(slide.id, pageWith(page, inputs, MODEL.evaluate(slide.runtime, inputs, "direct", action.id), null, null));
      } else if (action.type === "SET_PANEL") {
        invariant(slide.runtime.scene.type === "drilldown" || slide.runtime.scene.type === "accordion", "E_ACTION_PANEL");
        var panelIds = slide.runtime.scene.states.panels.map(function (panel) { return panel.id; });
        invariant(action.panel === null || panelIds.indexOf(action.panel) >= 0, "E_ACTION_PANEL");
        var panelInputs = new Map(page.inputs);
        panelInputs.set("panel", action.panel);
        pages.set(slide.id, pageWith(page, panelInputs, MODEL.evaluate(slide.runtime, panelInputs, "direct", "panel"), null, null));
      } else if (action.type === "RESET_PAGE") {
        var resetInputs = new Map();
        var resetEvidence = null;
        if (slide.runtime.scene.type === "evidence_only") {
          resetEvidence = slide.runtime.scene.initialState.evidence;
          resetInputs.set("evidence", resetEvidence);
        } else if (slide.runtime.scene.type === "drilldown" || slide.runtime.scene.type === "accordion") {
          resetInputs.set("panel", slide.runtime.scene.initialState.panel);
        } else {
          for (var resetIndex = 0; resetIndex < slide.runtime.controlList.length; resetIndex += 1) {
            var resetControl = slide.runtime.controlList[resetIndex];
            var resetValue = slide.runtime.scene.initialState[resetControl.id];
            resetInputs.set(resetControl.id, resetControl.kind === "range" ? DECIMAL.parse(resetValue, slide.runtime.scene.scale) : resetValue);
          }
        }
        pages.set(slide.id, pageWith(page, resetInputs, MODEL.evaluate(slide.runtime, resetInputs, "reset", null), "live", null));
        if (resetEvidence !== null) {
          return result(state, pages, resetEvidence === "closed" ? [] : [Object.freeze({ kind: "evidence", ordinal: slide.ordinal, tab: resetEvidence === "both" ? (slide.runtime.scene.evidence.sources.length ? "sources" : "assumptions") : resetEvidence })], null, null);
        }
      } else if (action.type === "RESTORE_FRAGMENT") {
        pages.set(slide.id, pageWith(page, action.inputs, MODEL.evaluate(slide.runtime, action.inputs, "restore", null), action.mode, null));
        if (slide.runtime.scene.type === "evidence_only") {
          var restoredEvidence = action.inputs.get("evidence");
          return result(state, pages, restoredEvidence === "closed" ? [] : [Object.freeze({ kind: "evidence", ordinal: slide.ordinal, tab: restoredEvidence === "both" ? (slide.runtime.scene.evidence.sources.length ? "sources" : "assumptions") : restoredEvidence })], null, null);
        }
        return result(state, pages, [], null, null);
      } else if (action.type === "SET_MODE") {
        invariant(action.mode === "live" || action.mode === "static", "E_ACTION_MODE");
        pages.set(slide.id, pageWith(page, null, null, action.mode, null));
      } else if (action.type === "OPEN_EVIDENCE") {
        if (slide.runtime.scene.type === "evidence_only") {
          var evidenceInputs = new Map(page.inputs);
          evidenceInputs.set("evidence", action.tab);
          pages.set(slide.id, pageWith(page, evidenceInputs, MODEL.evaluate(slide.runtime, evidenceInputs, "direct", "evidence"), null, null));
        }
        var evidenceOverlays = state.overlays.slice();
        evidenceOverlays.push(Object.freeze({ kind: "evidence", ordinal: slide.ordinal, tab: action.tab }));
        return result(state, pages, evidenceOverlays, null, null);
      } else if (action.type === "SET_EVIDENCE_TAB") {
        var evidenceTop = top(state);
        invariant(evidenceTop && evidenceTop.kind === "evidence", "E_ACTION_OVERLAY");
        if (slide.runtime.scene.type === "evidence_only") {
          var tabInputs = new Map(page.inputs);
          tabInputs.set("evidence", action.tab);
          pages.set(slide.id, pageWith(page, tabInputs, MODEL.evaluate(slide.runtime, tabInputs, "direct", "evidence"), null, null));
        }
        var changedOverlays = state.overlays.slice();
        changedOverlays[changedOverlays.length - 1] = Object.freeze({ kind: "evidence", ordinal: evidenceTop.ordinal, tab: action.tab });
        return result(state, pages, changedOverlays, null, null);
      } else if (action.type === "FAIL_SCENE") {
        pages.set(slide.id, pageWith(page, null, null, "static", action.code));
        return result(state, pages, [], null, null);
      } else {
        invariant(false, "E_ACTION_UNKNOWN");
      }
      return result(state, pages, state.overlays, null, null);
    }
    return Object.freeze({ reduce: reduce });
  }());

  var URL_STATE = (function () {
    function runtimeControls(runtime) {
      if (Array.isArray(runtime.controlList)) {
        return runtime.controlList;
      }
      return runtime.control ? [runtime.control] : [];
    }
    function sceneType(runtime) {
      return runtime.scene.type || "slider_model";
    }
    function rangeControl(control) {
      return control.kind === undefined || control.kind === "range";
    }
    function malformedPercent(value) {
      for (var index = 0; index < value.length; index += 1) {
        if (value.charAt(index) === "%" && !/^[0-9A-Fa-f]{2}$/.test(value.slice(index + 1, index + 3))) {
          return true;
        }
      }
      return false;
    }
    function slideIndex(value, length) {
      invariant(/^[+-]?[0-9]+$/.test(value), "E_FRAGMENT_SLIDE");
      var parsed = BigInt(value);
      return parsed < BigInt(1) ? 0 : parsed > BigInt(length) ? length - 1 : Number(parsed - BigInt(1));
    }
    function initialValues(index, deck) {
      var slide = deck.slides[index];
      if (!slide.runtime) {
        return null;
      }
      var values = new Map();
      if (sceneType(slide.runtime) === "evidence_only") {
        values.set("evidence", slide.runtime.scene.initialState.evidence);
        return values;
      }
      if (sceneType(slide.runtime) === "drilldown" || sceneType(slide.runtime) === "accordion") {
        values.set("panel", slide.runtime.scene.initialState.panel);
        return values;
      }
      var controls = runtimeControls(slide.runtime);
      for (var controlIndex = 0; controlIndex < controls.length; controlIndex += 1) {
        var control = controls[controlIndex];
        var initialValue = slide.runtime.scene.initialState[control.id];
        values.set(control.id, rangeControl(control) ? DECIMAL.parse(initialValue, slide.runtime.scene.scale) : initialValue);
      }
      return values;
    }
    function invalidResult(index, deck) {
      return { index: index, valid: false, values: initialValues(index, deck), mode: "live" };
    }
    function rawSlideIndex(raw, deck) {
      var parts = raw.split("&");
      for (var index = 0; index < parts.length; index += 1) {
        var equals = parts[index].indexOf("=");
        var rawKey = equals < 0 ? parts[index] : parts[index].slice(0, equals);
        if (malformedPercent(rawKey)) {
          continue;
        }
        var key;
        try {
          key = decodeURIComponent(rawKey.replace(/\+/g, " "));
        } catch (ignoredKey) {
          continue;
        }
        if (key !== "slide") {
          continue;
        }
        var rawValue = equals < 0 ? "" : parts[index].slice(equals + 1);
        if (malformedPercent(rawValue)) {
          return 0;
        }
        try {
          return slideIndex(decodeURIComponent(rawValue.replace(/\+/g, " ")), deck.slides.length);
        } catch (ignoredSlide) {
          return 0;
        }
      }
      return 0;
    }
    function parse(hash, deck) {
      if (typeof hash !== "string" || hash.length > 4097) {
        return invalidResult(0, deck);
      }
      var raw = hash.charAt(0) === "#" ? hash.slice(1) : hash;
      if (!raw) {
        return { index: 0, valid: true, values: null, mode: "live" };
      }
      if (/^[0-9]+$/.test(raw)) {
        var legacyIndex = slideIndex(raw, deck.slides.length);
        return { index: legacyIndex, valid: true, values: initialValues(legacyIndex, deck), mode: "live" };
      }
      var local = raw.match(/^idrt-page-([0-9]+)$/);
      if (local) {
        var localIndex = slideIndex(local[1], deck.slides.length);
        return { index: localIndex, valid: true, values: initialValues(localIndex, deck), mode: "live" };
      }
      if (raw.split("&").length > 10) {
        return invalidResult(0, deck);
      }
      var rawIndex = rawSlideIndex(raw, deck);
      if (malformedPercent(raw)) {
        return invalidResult(rawIndex, deck);
      }
      var parameters = new URLSearchParams(raw);
      var seen = new Set();
      var duplicate = false;
      parameters.forEach(function (value, key) {
        if (seen.has(key)) {
          duplicate = true;
        }
        seen.add(key);
      });
      if (!seen.has("slide")) {
        return invalidResult(0, deck);
      }
      var index;
      try {
        index = slideIndex(parameters.get("slide"), deck.slides.length);
      } catch (failure) {
        return invalidResult(0, deck);
      }
      var slide = deck.slides[index];
      var allowed = new Set(["slide", "mode"]);
      if (slide.runtime) {
        if (sceneType(slide.runtime) === "evidence_only") {
          allowed.add("evidence");
        } else if (sceneType(slide.runtime) === "drilldown" || sceneType(slide.runtime) === "accordion") {
          allowed.add("panel");
        } else {
          var allowedControls = runtimeControls(slide.runtime);
          for (var allowedIndex = 0; allowedIndex < allowedControls.length; allowedIndex += 1) { allowed.add(allowedControls[allowedIndex].id); }
        }
      }
      var valid = !duplicate;
      seen.forEach(function (key) { if (!allowed.has(key)) { valid = false; } });
      var mode = parameters.has("mode") ? parameters.get("mode") : "live";
      if (mode !== "live" && mode !== "static") {
        valid = false;
        mode = "live";
      }
      var values = null;
      if (slide.runtime) {
        values = new Map();
        if (sceneType(slide.runtime) === "evidence_only") {
          var evidenceMode = parameters.has("evidence") ? parameters.get("evidence") : slide.runtime.scene.initialState.evidence;
          var evidenceModes = ["closed"];
          if (slide.runtime.scene.evidence.sources.length) { evidenceModes.push("sources"); }
          if (slide.runtime.scene.evidence.assumptions.length) { evidenceModes.push("assumptions"); }
          if (slide.runtime.scene.evidence.sources.length && slide.runtime.scene.evidence.assumptions.length) { evidenceModes.push("both"); }
          if (evidenceModes.indexOf(evidenceMode) < 0) { valid = false; }
          values.set("evidence", valid ? evidenceMode : slide.runtime.scene.initialState.evidence);
        } else if (sceneType(slide.runtime) === "drilldown" || sceneType(slide.runtime) === "accordion") {
          var panelValue = parameters.has("panel") ? parameters.get("panel") : slide.runtime.scene.initialState.panel;
          var panelValues = slide.runtime.scene.states.panels.map(function (panel) { return panel.id; });
          if (panelValue !== null && panelValues.indexOf(panelValue) < 0) { valid = false; }
          values.set("panel", valid ? panelValue : slide.runtime.scene.initialState.panel);
        } else {
          var parseControls = runtimeControls(slide.runtime);
          for (var parseControlIndex = 0; parseControlIndex < parseControls.length; parseControlIndex += 1) {
            var control = parseControls[parseControlIndex];
            var rawControlValue = parameters.has(control.id) ? parameters.get(control.id) : slide.runtime.scene.initialState[control.id];
            if (rangeControl(control)) {
              try {
                values.set(control.id, DECIMAL.snap(rawControlValue, control, slide.runtime.scene.scale));
              } catch (failure) {
                valid = false;
              }
            } else if (slide.runtime.controlDomains.get(control.id).indexOf(rawControlValue) >= 0) {
              values.set(control.id, rawControlValue);
            } else {
              valid = false;
            }
          }
        }
        if (!valid) {
          values = initialValues(index, deck);
          mode = "live";
        }
      } else if (seen.size > 1) {
        valid = false;
      }
      return { index: index, valid: valid, values: values, mode: mode };
    }
    function serialize(state, deck) {
      var slide = deck.slides[state.currentIndex];
      var parts = ["slide=" + String(state.currentIndex + 1)];
      var page = state.pages.get(slide.id);
      if (slide.runtime && page) {
        if (sceneType(slide.runtime) === "evidence_only") {
          parts.push("evidence=" + encodeURIComponent(page.inputs.get("evidence")));
        } else if (sceneType(slide.runtime) === "drilldown" || sceneType(slide.runtime) === "accordion") {
          if (page.inputs.get("panel") !== null) { parts.push("panel=" + encodeURIComponent(page.inputs.get("panel"))); }
        } else {
          var serializeControls = runtimeControls(slide.runtime);
          for (var controlIndex = 0; controlIndex < serializeControls.length; controlIndex += 1) {
            var control = serializeControls[controlIndex];
            var value = page.inputs.get(control.id);
            parts.push(encodeURIComponent(control.id) + "=" + encodeURIComponent(rangeControl(control) ? DECIMAL.canonical(value, slide.runtime.scene.scale) : value));
          }
        }
        if (page.viewMode === "static") {
          parts.push("mode=static");
        }
      }
      return "#" + parts.join("&");
    }
    return Object.freeze({ parse: parse, serialize: serialize });
  }());

  var VIEW = (function () {
    function nodes(slide) {
      var section = document.getElementById("idrt-page-" + slide.ordinal);
      invariant(section, "E_DOM_SECTION");
      var result = {
        section: section,
        heading: document.getElementById("idrt-heading-" + slide.ordinal),
        fallback: section.querySelector(".fallback-layer"),
        live: section.querySelector(".live-layer"),
        rail: section.querySelector(".control-rail"),
        status: document.getElementById("idrt-status-" + slide.ordinal),
        reset: document.getElementById("idrt-reset-" + slide.ordinal),
        evidence: document.getElementById("idrt-evidence-open-" + slide.ordinal),
        toggle: document.getElementById("idrt-static-toggle-" + slide.ordinal),
        dialog: document.getElementById("idrt-evidence-dialog-" + slide.ordinal),
        output: section.querySelector("[data-live-value]"),
        decisionStatus: section.querySelector("[data-decision-status]"),
        recommendation: section.querySelector("[data-decision-recommendation]")
      };
      if (slide.runtime) {
        result.staticSummary = section.querySelector(".scene-summary");
        result.liveSummary = section.querySelector(".live-summary");
        result.semanticView = section.querySelector("[data-view-component]");
        result.panelSurface = section.querySelector(".panel-surface");
        result.controls = new Map();
        var controlList = slide.runtime.controlList || (slide.runtime.control ? [slide.runtime.control] : []);
        for (var controlIndex = 0; controlIndex < controlList.length; controlIndex += 1) {
          var control = controlList[controlIndex];
          var wrapper = section.querySelector('[data-control-id="' + control.id + '"]');
          invariant(wrapper, "E_DOM_SCENE");
          var controlDom = {
            wrapper: wrapper,
            range: control.kind === "range" ? (wrapper.matches('input[type="range"]') ? wrapper : wrapper.querySelector('input[type="range"]')) : null,
            select: control.kind === "select" ? (wrapper.matches("select") ? wrapper : wrapper.querySelector("select")) : null,
            buttons: wrapper.querySelectorAll("[data-control-value]"),
            value: document.getElementById("idrt-control-value-" + slide.ordinal + "-" + String(controlIndex + 1))
          };
          invariant((control.kind !== "range" || controlDom.range) && (control.kind !== "select" || controlDom.select) && (["segmented", "toggle"].indexOf(control.kind) < 0 || controlDom.buttons.length === control.options.length), "E_DOM_SCENE");
          result.controls.set(control.id, controlDom);
        }
        result.input = slide.runtime.control && result.controls.has(slide.runtime.control.id) ? result.controls.get(slide.runtime.control.id).range : null;
        result.controlValue = slide.runtime.control && result.controls.has(slide.runtime.control.id) ? result.controls.get(slide.runtime.control.id).value : null;
        invariant(result.fallback && result.live && result.staticSummary && result.liveSummary && result.rail && result.status && result.reset && result.evidence && result.toggle && result.dialog, "E_DOM_SCENE");
        if (slide.runtime.scene.type === "state_toggle") { invariant(result.semanticView, "E_DOM_SCENE"); }
        if (slide.runtime.scene.type === "drilldown" || slide.runtime.scene.type === "accordion") { invariant(result.panelSurface, "E_DOM_SCENE"); }
        if (slide.runtime.scene.decisionContract) { invariant(result.output && result.decisionStatus && result.recommendation, "E_DOM_SCENE"); }
      }
      return result;
    }
    function setControlDisabled(dom, disabled) {
      dom.controls.forEach(function (controlDom) {
        if (controlDom.range) { controlDom.range.disabled = disabled; }
        if (controlDom.select) { controlDom.select.disabled = disabled; }
        for (var buttonIndex = 0; buttonIndex < controlDom.buttons.length; buttonIndex += 1) { controlDom.buttons[buttonIndex].disabled = disabled; }
      });
      if (dom.panelSurface) {
        var panelButtons = dom.panelSurface.querySelectorAll("button");
        for (var panelButtonIndex = 0; panelButtonIndex < panelButtons.length; panelButtonIndex += 1) { panelButtons[panelButtonIndex].disabled = disabled; }
      }
      var tooltipTriggers = dom.section.querySelectorAll("[data-tooltip-for]");
      for (var tooltipIndex = 0; tooltipIndex < tooltipTriggers.length; tooltipIndex += 1) {
        tooltipTriggers[tooltipIndex].disabled = disabled;
        tooltipTriggers[tooltipIndex].setAttribute("aria-disabled", disabled ? "true" : "false");
      }
    }

    function selectedOptionLabel(control, value) {
      for (var optionIndex = 0; optionIndex < control.options.length; optionIndex += 1) {
        if (control.options[optionIndex].value === value) { return control.options[optionIndex].label; }
      }
      invariant(false, "E_DOM_CONTROL");
    }

    function paintControls(slide, page, dom) {
      var programControls = slide.runtime.scene.narration.program.controls || [];
      var atoms = new Map();
      for (var atomIndex = 0; atomIndex < programControls.length; atomIndex += 1) { atoms.set(programControls[atomIndex].id, programControls[atomIndex]); }
      var controlList = slide.runtime.controlList || [];
      for (var controlIndex = 0; controlIndex < controlList.length; controlIndex += 1) {
        var control = controlList[controlIndex];
        var controlDom = dom.controls.get(control.id);
        var value = page.inputs.get(control.id);
        if (control.kind === "range") {
          controlDom.range.value = DECIMAL.indexOf(value, control, slide.runtime.scene.scale);
          controlDom.range.setAttribute("aria-valuetext", DECIMAL.canonical(value, slide.runtime.scene.scale));
          var atom = atoms.get(control.id);
          if (controlDom.value && atom) { controlDom.value.textContent = DECIMAL.format(value, slide.runtime.scene.scale, atom.display, Math.max(DECIMAL.scaleOf(control.min), DECIMAL.scaleOf(control.step)), false); }
        } else {
          if (controlDom.select) { controlDom.select.value = value; }
          for (var buttonIndex = 0; buttonIndex < controlDom.buttons.length; buttonIndex += 1) {
            controlDom.buttons[buttonIndex].setAttribute("aria-pressed", controlDom.buttons[buttonIndex].getAttribute("data-control-value") === value ? "true" : "false");
          }
          if (controlDom.value) { controlDom.value.textContent = selectedOptionLabel(control, value); }
        }
      }
    }

    function paintOutputs(slide, page, dom) {
      var outputNodes = dom.section.querySelectorAll("[data-live-value]");
      for (var outputIndex = 0; outputIndex < outputNodes.length; outputIndex += 1) {
        var outputId = outputNodes[outputIndex].getAttribute("data-live-value");
        if (!page.evaluation.outputTexts.has(outputId)) { continue; }
        var value = page.evaluation.outputs.get(outputId);
        outputNodes[outputIndex].textContent = page.evaluation.outputTexts.get(outputId);
        if (typeof value === "bigint") {
          outputNodes[outputIndex].setAttribute("data-canonical-value", DECIMAL.canonical(value, slide.runtime.scene.scale));
          var definition = slide.runtime.definitions.get(outputId);
          if (definition && definition.kind === "numeric") { outputNodes[outputIndex].setAttribute("data-quantity", slide.runtime.quantities.get(definition.quantity).unit); }
        }
      }
      if (page.evaluation.decision) {
        dom.decisionStatus.textContent = page.evaluation.decision.status;
        dom.recommendation.textContent = page.evaluation.decision.recommendation;
      }
    }

    function liveSvgId(prefix, itemId, index) {
      var candidate = prefix + "-" + itemId;
      if (candidate.length <= 64) { return candidate; }
      var digest = 2166136261;
      for (var characterIndex = 0; characterIndex < itemId.length; characterIndex += 1) {
        digest ^= itemId.charCodeAt(characterIndex);
        digest = Math.imul(digest, 16777619);
      }
      return prefix + "Key-" + (digest >>> 0).toString(16).padStart(8, "0");
    }

    function liveSvgNode(slide, rawId, tagName) {
      var node = document.getElementById("idsvg-" + slide.ordinal + "-live-shell-" + rawId);
      invariant(node && node.tagName.toLowerCase() === tagName, "E_DOM_LIVE_VIEW");
      return node;
    }

    function resolvedViewNumber(slide, row, slot) {
      if (own(row, slot + "Value")) { return row[slot + "Value"]; }
      invariant(plain(row[slot]) && typeof row[slot].value === "string", "E_DOM_LIVE_VIEW");
      return DECIMAL.parse(row[slot].value, slide.runtime.scene.scale);
    }

    function livePrimaryColor(scene) {
      var palette = scene.invariants.palette || "navy";
      if (palette === "red") { return "#B4232D"; }
      if (palette === "green") { return "#176B50"; }
      if (palette === "mono") { return "#202124"; }
      return "#15296B";
    }

    function paintRankBridge(slide, page, animatedRanks) {
      var scene = slide.runtime.scene;
      var base = scene.initialEvaluation.view.items;
      var items = page.evaluation.view.items;
      var compact = window.matchMedia("(max-width: 760px), (orientation: portrait)").matches;
      var gap = Math.min(110, 330 / Math.max(1, items.length - 1));
      var start = compact ? 280 : 300;
      var focus = null;
      function textNode(prefix, item, index, x, y, size, anchor, value) {
        var node = liveSvgNode(slide, liveSvgId(prefix, item.id, index), "text");
        node.setAttribute("x", String(x)); node.setAttribute("y", String(y));
        node.setAttribute("font-size", String(size)); node.setAttribute("text-anchor", anchor);
        if (value !== undefined) { node.textContent = value; }
        return node;
      }
      for (var index = 0; index < base.length; index += 1) {
        var initial = base[index];
        var current = items.find(function (row) { return row.id === initial.id; });
        invariant(current, "E_DOM_LIVE_VIEW");
        var initialY = start + (initial.rank - 1) * gap;
        var currentY = start + ((animatedRanks ? animatedRanks.get(current.id) : current.rank) - 1) * gap;
        var connector = liveSvgNode(slide, liveSvgId("LiveBridge", initial.id, index), "line");
        connector.setAttribute("x1", compact ? "151" : "420");
        connector.setAttribute("x2", compact ? "239" : "860");
        connector.setAttribute("y1", String(initialY)); connector.setAttribute("y2", String(currentY));
        if (connector.getAttribute("stroke-width") === "5") { focus = current; }
        [initial, current].forEach(function (item, side) {
          var isBase = side === 0;
          var prefix = isBase ? "LiveBase" : "Live";
          var x = compact ? (isBase ? 20 : 251) : (isBase ? 100 : 900);
          var y = isBase ? initialY : currentY;
          var shortLabel = item.label.replace(/ route$/, "");
          var numeric = DECIMAL.canonical(resolvedViewNumber(slide, item, "metric"), scene.scale);
          textNode(prefix + "Rank", item, index, x, compact ? y - 27 : y, compact ? 20 : 22, "start", "#" + item.rank);
          textNode(prefix + "Value", item, index, compact ? x : x + 48, y, compact ? 22 : 30, "start", shortLabel);
          textNode(prefix + "Metric", item, index, compact ? x : x + 292, compact ? y + 36 : y + 3, compact ? 30 : 40, compact ? "start" : "end", numeric);
          var unit = textNode(prefix + "Unit", item, index, compact ? x + 44 : x + 292, compact ? y + 34 : y + 31, compact ? 15 : 20, compact ? "start" : "end");
          unit.textContent = "";
        });
      }
      var heading = liveSvgNode(slide, "LiveCurrentHeading", "text");
      var selected = page.inputs.get(scene.controls[0].id);
      var option = scene.controls[0].options.find(function (item) { return item.value === selected; });
      heading.textContent = compact ? (scene.locale === "ja" ? "選択した条件" : "Selected") : option.label;
      heading.setAttribute("x", compact ? "251" : "900"); heading.setAttribute("font-size", compact ? "21" : "24");
      var baselineHeading = liveSvgNode(slide, "LiveDomainStart", "text");
      baselineHeading.setAttribute("x", compact ? "20" : "100"); baselineHeading.setAttribute("font-size", compact ? "21" : "24");
      var domain = liveSvgNode(slide, "LiveDomainEnd", "text");
      domain.setAttribute("x", compact ? "20" : "100"); domain.setAttribute("font-size", compact ? "17" : "20");
      domain.setAttribute("y", compact ? "225" : "238");
      var deltaNode = liveSvgNode(slide, "LiveDelta", "text");
      deltaNode.setAttribute("x", compact ? "20" : "100"); deltaNode.setAttribute("y", compact ? "580" : "595");
      deltaNode.setAttribute("font-size", compact ? "20" : "28");
      if (focus) {
        var baseline = base.find(function (item) { return item.id === focus.id; });
        var delta = resolvedViewNumber(slide, focus, "metric") - resolvedViewNumber(slide, baseline, "metric");
        var rankChange = baseline.rank - focus.rank;
        var name = focus.label.replace(/ route$/, "");
        var difference = DECIMAL.canonical(delta, scene.scale);
        var movement = rankChange > 0 ? " rises to #" : rankChange < 0 ? " falls to #" : " stays at #";
        deltaNode.textContent = name + movement + focus.rank + (delta === BigInt(0) ? " · baseline score" : " · " + (delta > BigInt(0) ? "+" : "") + difference + " points");
      }
    }

    function paintSvgView(slide, page) {
      var view = page.evaluation.view;
      if (!view) { return; }
      if (view.component === "bar_compare") {
        var barMinimum = DECIMAL.parse(view.domain[0], slide.runtime.scene.scale);
        var barMaximum = DECIMAL.parse(view.domain[1], slide.runtime.scene.scale);
        var barGap = Math.min(76, 300 / Math.max(1, view.items.length));
        var barCompact = view.items.length > 6;
        var barLabelOffset = barCompact ? 12 : 18;
        var barOffset = barCompact ? 16 : 24;
        var barHeight = barCompact ? 7 : 24;
        for (var barIndex = 0; barIndex < view.items.length; barIndex += 1) {
          var barItem = view.items[barIndex];
          var barValue = resolvedViewNumber(slide, barItem, "value");
          var barWidth = Math.max(0, Math.min(620, 620 * DECIMAL.fraction(barValue, barMinimum, barMaximum)));
          var barY = 232 + barIndex * barGap;
          var barMark = liveSvgNode(slide, liveSvgId("LiveMark", barItem.id, barIndex), "rect");
          var barName = liveSvgNode(slide, liveSvgId("LiveLabel", barItem.id, barIndex), "text");
          var barLabel = liveSvgNode(slide, liveSvgId("LiveValue", barItem.id, barIndex), "text");
          barMark.setAttribute("width", barWidth.toFixed(1));
          barMark.setAttribute("y", (barY + barOffset).toFixed(1));
          barMark.setAttribute("opacity", barItem.removed ? "0.35" : "1");
          barName.setAttribute("y", (barY + barLabelOffset).toFixed(1));
          barName.setAttribute("font-weight", barItem.emphasis ? "600" : "normal");
          barLabel.setAttribute("x", Math.min(800, 100 + barWidth + 12).toFixed(1));
          barLabel.setAttribute("y", (barY + barOffset + barHeight).toFixed(1));
          barLabel.textContent = barItem.valueText;
        }
        return;
      }
      if (view.component === "ranked_list") {
        if (document.getElementById("idrt-page-" + slide.ordinal).getAttribute("data-visual-layout") === "rank_bridge") {
          paintRankBridge(slide, page);
          return;
        }
        var rankGap = Math.min(104, 320 / Math.max(1, view.items.length));
        var rankTextOffset = view.items.length > 6 ? 14 : 26;
        for (var rankIndex = 0; rankIndex < view.items.length; rankIndex += 1) {
          var rankItem = view.items[rankIndex];
          var rankY = 246 + (rankItem.rank - 1) * rankGap;
          var rankMark = liveSvgNode(slide, liveSvgId("LiveMark", rankItem.id, rankIndex), "g");
          var rankRect = rankMark.querySelector("rect");
          var rankLabel = liveSvgNode(slide, liveSvgId("LiveValue", rankItem.id, rankIndex), "text");
          invariant(rankRect, "E_DOM_LIVE_VIEW");
          rankMark.setAttribute("opacity", rankItem.removed ? "0.35" : "1");
          rankRect.setAttribute("y", (rankY + rankTextOffset + 13).toFixed(1));
          if (view.domain && rankItem.metric) {
            var rankMin = DECIMAL.parse(view.domain[0], slide.runtime.scene.scale);
            var rankMax = DECIMAL.parse(view.domain[1], slide.runtime.scene.scale);
            var rankWidth = 690 * DECIMAL.fraction(resolvedViewNumber(slide, rankItem, "metric"), rankMin, rankMax);
            rankRect.setAttribute("width", Math.max(0, Math.min(690, rankWidth)).toFixed(1));
          }
          rankLabel.setAttribute("y", (rankY + rankTextOffset).toFixed(1));
          rankLabel.setAttribute("font-weight", rankItem.emphasis ? "600" : "normal");
          var rankText = String(rankItem.rank) + " · " + rankItem.label;
          if (rankItem.removed) { rankText += slide.runtime.scene.locale === "ja" ? " · 除外" : " · removed"; }
          rankLabel.textContent = rankText;
          var rankMetric = liveSvgNode(slide, liveSvgId("LiveMetric", rankItem.id, rankIndex), "text");
          rankMetric.setAttribute("y", (rankY + rankTextOffset).toFixed(1));
          rankMetric.textContent = rankItem.metricText || "";
        }
        return;
      }
      if (view.component === "recommendation_panel") {
        var bands = slide.runtime.scene.model.bands;
        var scoreMinimum = DECIMAL.parse(bands[0].min.value, slide.runtime.scene.scale);
        var scoreMaximum = DECIMAL.parse(bands[bands.length - 1].max.value, slide.runtime.scene.scale);
        var scoreX = 100 + 700 * DECIMAL.fraction(view.score.value, scoreMinimum, scoreMaximum);
        var cursor = liveSvgNode(slide, "LiveScoreCursor", "line");
        cursor.setAttribute("x1", scoreX.toFixed(1));
        cursor.setAttribute("x2", scoreX.toFixed(1));
        var classification = page.evaluation.outputs.get("classification");
        for (var bandIndex = 0; bandIndex < bands.length; bandIndex += 1) {
          var band = liveSvgNode(slide, liveSvgId("LiveBand", bands[bandIndex].id, bandIndex), "rect");
          band.setAttribute("opacity", bands[bandIndex].label === classification ? "0.9" : "0.35");
        }
        liveSvgNode(slide, "LiveScoreValue", "text").textContent = view.scoreText;
        liveSvgNode(slide, "LiveClassification", "text").textContent = classification;
        var contributions = slide.runtime.scene.model.contributions;
        var contributionMaximum = BigInt(0);
        contributions.forEach(function (entry) { entry[1].forEach(function (pair) { var value = DECIMAL.parse(pair[1].value, slide.runtime.scene.scale); if (value > contributionMaximum) { contributionMaximum = value; } }); });
        contributions.forEach(function (entry, index) {
          var selected = page.inputs.get(entry[0]);
          var selector = typeof selected === "bigint" ? DECIMAL.canonical(selected, slide.runtime.scene.scale) : selected;
          var pair = entry[1].find(function (candidate) { return candidate[0] === selector; });
          invariant(pair, "E_MODEL_INPUT");
          var value = DECIMAL.parse(pair[1].value, slide.runtime.scene.scale);
          var width = contributionMaximum === BigInt(0) ? 0 : 360 * DECIMAL.fraction(value, BigInt(0), contributionMaximum);
          liveSvgNode(slide, liveSvgId("LiveContribution", entry[0], index), "rect").setAttribute("width", width.toFixed(1));
          liveSvgNode(slide, liveSvgId("LiveContributionValue", entry[0], index), "text").textContent = DECIMAL.canonical(value, slide.runtime.scene.scale);
        });
        return;
      }
      invariant(view.component === "dot_plot", "E_DOM_LIVE_VIEW");
      for (var pointIndex = 0; pointIndex < view.points.length; pointIndex += 1) {
        var point = view.points[pointIndex];
        var pointMark = liveSvgNode(slide, point.id, "circle");
        var pointLabelId = liveSvgId("LivePointLabel", point.id, pointIndex);
        var pointLabel = liveSvgNode(slide, pointLabelId, "text");
        pointMark.setAttribute("r", point.highlight ? "9" : "7");
        pointMark.setAttribute("fill", point.highlight ? livePrimaryColor(slide.runtime.scene) : "#6B7280");
        pointMark.setAttribute("opacity", point.removed ? "0.35" : "1");
        pointLabel.setAttribute("fill", point.highlight ? "#000000" : "#374151");
        pointLabel.setAttribute("font-weight", point.highlight ? "600" : "normal");
        pointLabel.setAttribute("opacity", point.removed ? "0.35" : "1");
        var visibleLabel = slide.runtime.scene.type === "slider_model" && view.points.length === 1 ? point.xText + " · " + point.yText : point.label;
        pointLabel.textContent = visibleLabel + (point.removed ? (slide.runtime.scene.locale === "ja" ? " · 除外" : " · Removed") : "");
        pointLabel.setAttribute("data-label-width", String(Math.min(700, visibleLabel.length * 22 * 0.62)));
      }
    }

    function paintView(slide, page, dom) {
      if (!dom.semanticView || !page.evaluation.view) { return; }
      var view = page.evaluation.view;
      invariant(dom.semanticView.getAttribute("data-view-component") === view.component, "E_DOM_VIEW");
      paintSvgView(slide, page);
      if (view.component === "recommendation_panel") {
        var score = dom.semanticView.querySelector("[data-view-score]");
        invariant(score, "E_DOM_VIEW");
        score.textContent = view.scoreText;
        return;
      }
      var collection = view.component === "dot_plot" ? view.points : view.items;
      for (var itemIndex = 0; itemIndex < collection.length; itemIndex += 1) {
        var item = collection[itemIndex];
        var node = dom.semanticView.querySelector('[data-view-item-id="' + item.id + '"]');
        invariant(node, "E_DOM_VIEW");
        dom.semanticView.appendChild(node);
        node.setAttribute("data-removed", item.removed ? "true" : "false");
        node.setAttribute("data-emphasis", (own(item, "emphasis") ? item.emphasis : item.highlight) ? "true" : "false");
        var label = node.querySelector("[data-view-label]");
        if (label) { label.textContent = item.label; }
        var tooltipText = item.label;
        if (view.component === "bar_compare") {
          var valueNode = node.querySelector("[data-view-value]");
          valueNode.textContent = item.valueText;
          tooltipText += "; " + item.valueText;
        } else if (view.component === "ranked_list") {
          node.querySelector("[data-view-rank]").textContent = String(item.rank);
          var metricNode = node.querySelector("[data-view-metric]");
          if (metricNode && item.metricText) { metricNode.textContent = item.metricText; }
          tooltipText = String(item.rank) + "; " + item.label + (item.metricText ? "; " + item.metricText : "");
        } else {
          node.querySelector("[data-view-x]").textContent = view.xLabel + ": " + item.xText;
          node.querySelector("[data-view-y]").textContent = view.yLabel + ": " + item.yText;
          tooltipText += "; " + view.xLabel + ": " + item.xText + "; " + view.yLabel + ": " + item.yText;
        }
        var removal = node.querySelector("[data-view-removal]");
        invariant(removal, "E_DOM_VIEW");
        removal.hidden = !item.removed;
        removal.textContent = slide.runtime.scene.locale === "ja" ? "除外" : "removed";
        if (item.removed) { tooltipText += slide.runtime.scene.locale === "ja" ? "; 除外" : "; removed"; }
        var tooltipTrigger = node.querySelector("[data-tooltip-for]");
        if (tooltipTrigger) {
          var tooltip = document.getElementById(tooltipTrigger.getAttribute("aria-controls"));
          invariant(tooltip, "E_DOM_VIEW");
          tooltip.textContent = tooltipText;
        }
      }
    }

    function paintPanels(slide, page, dom) {
      if (!dom.panelSurface) { return; }
      var selected = page.inputs.get("panel");
      if (slide.runtime.scene.type === "drilldown") {
        var openers = dom.panelSurface.querySelectorAll('[data-action="open-panel"]');
        for (var openerIndex = 0; openerIndex < openers.length; openerIndex += 1) { openers[openerIndex].setAttribute("aria-expanded", openers[openerIndex].getAttribute("data-panel-target") === selected ? "true" : "false"); }
        var drillPanels = dom.panelSurface.querySelectorAll("[data-panel-id]");
        for (var drillIndex = 0; drillIndex < drillPanels.length; drillIndex += 1) { drillPanels[drillIndex].hidden = drillPanels[drillIndex].getAttribute("data-panel-id") !== selected; }
      } else {
        var accordionButtons = dom.panelSurface.querySelectorAll("[data-accordion-id]");
        for (var accordionIndex = 0; accordionIndex < accordionButtons.length; accordionIndex += 1) {
          var expanded = accordionButtons[accordionIndex].getAttribute("data-accordion-id") === selected;
          accordionButtons[accordionIndex].setAttribute("aria-expanded", expanded ? "true" : "false");
          var panel = document.getElementById(accordionButtons[accordionIndex].getAttribute("aria-controls"));
          invariant(panel, "E_DOM_PANEL");
          panel.hidden = !expanded;
        }
      }
    }

    function baseline(slide, page, dom, labels, printPage) {
      dom.section.setAttribute("data-view-mode", "static");
      var failed = Boolean(page.failed);
      var displayPage = printPage || page;
      dom.fallback.hidden = false;
      dom.live.hidden = true;
      dom.staticSummary.hidden = false;
      dom.staticSummary.removeAttribute("aria-hidden");
      dom.liveSummary.hidden = true;
      dom.liveSummary.setAttribute("aria-hidden", "true");
      if (dom.semanticView) { dom.semanticView.hidden = true; }
      if (dom.panelSurface) { dom.panelSurface.hidden = true; }
      dom.rail.hidden = false;
      setControlDisabled(dom, true);
      dom.reset.disabled = true;
      dom.evidence.disabled = true;
      dom.toggle.disabled = failed;
      dom.toggle.setAttribute("aria-pressed", "true");
      paintControls(slide, displayPage, dom);
      paintOutputs(slide, displayPage, dom);
      paintView(slide, displayPage, dom);
      paintPanels(slide, displayPage, dom);
      dom.toggle.textContent = labels.live;
      dom.status.textContent = failed ? labels.failure : slide.runtime.scene.narration.messages.initial;
    }
    function semantic(slide, page, dom, labels, printPage) {
      if (page.viewMode === "static" || page.failed) {
        baseline(slide, page, dom, labels, printPage);
        return;
      }
      dom.section.setAttribute("data-view-mode", "live");
      dom.status.textContent = page.evaluation.narration;
      dom.fallback.hidden = true;
      dom.live.hidden = false;
      dom.staticSummary.hidden = true;
      dom.staticSummary.setAttribute("aria-hidden", "true");
      dom.liveSummary.hidden = false;
      dom.liveSummary.removeAttribute("aria-hidden");
      dom.rail.hidden = false;
      if (dom.semanticView) { dom.semanticView.hidden = false; }
      if (dom.panelSurface) { dom.panelSurface.hidden = false; }
      paintControls(slide, page, dom);
      paintOutputs(slide, page, dom);
      paintView(slide, page, dom);
      paintPanels(slide, page, dom);
      setControlDisabled(dom, false);
      dom.reset.disabled = false;
      dom.evidence.disabled = false;
      dom.toggle.disabled = false;
      dom.toggle.setAttribute("aria-pressed", "false");
      dom.toggle.textContent = labels.static;
    }
    function geometry(slide, evaluation) {
      var points = [];
      for (var index = 0; index < evaluation.points.length; index += 1) {
        var point = evaluation.points[index];
        var node = document.getElementById("idsvg-" + slide.ordinal + "-live-shell-" + point.id);
        invariant(node && node.tagName.toLowerCase() === "circle", "E_DOM_GEOMETRY");
        var rawLabelId = liveSvgId("LivePointLabel", point.id, index);
        var label = document.getElementById("idsvg-" + slide.ordinal + "-live-shell-" + rawLabelId);
        invariant(label && label.tagName.toLowerCase() === "text", "E_DOM_GEOMETRY");
        var labelWidth = Number(label.getAttribute("data-label-width"));
        var radius = Number(node.getAttribute("r"));
        invariant(Number.isFinite(labelWidth) && labelWidth >= 0 && Number.isFinite(radius) && radius > 0, "E_DOM_GEOMETRY");
        points.push({
          id: point.id,
          node: node,
          label: label,
          labelWidth: labelWidth,
          radius: radius,
          x: point.x,
          y: point.y
        });
      }
      return points;
    }
    function paint(points, positions) {
      for (var index = 0; index < points.length; index += 1) {
        points[index].node.setAttribute("cx", positions[index].x.toFixed(1));
        points[index].node.setAttribute("cy", positions[index].y.toFixed(1));
        var point = points[index];
        var x = positions[index].x;
        var y = positions[index].y;
        var gap = point.radius + 8;
        var rightX = x + gap;
        var leftX = x - gap;
        var rightAvailable = 830 - rightX;
        var leftAvailable = leftX - 80;
        var labelX;
        if (point.labelWidth <= rightAvailable || (point.labelWidth > leftAvailable && rightAvailable >= leftAvailable)) {
          point.label.setAttribute("text-anchor", "start");
          labelX = Math.max(80, Math.min(830 - point.labelWidth, rightX));
        } else {
          point.label.setAttribute("text-anchor", "end");
          labelX = Math.min(830, Math.max(80 + point.labelWidth, leftX));
        }
        var labelY = y + 30;
        if (labelY + 4 > 560) {
          labelY = y - point.radius - 8;
        } else if (labelY - 22 < 230) {
          labelY = y + point.radius + 22;
        }
        labelY = Math.min(556, Math.max(252, labelY));
        point.label.setAttribute("x", labelX.toFixed(1));
        point.label.setAttribute("y", labelY.toFixed(1));
      }
    }
    return Object.freeze({ nodes: nodes, semantic: semantic, baseline: baseline, geometry: geometry, paint: paint, paintBridge: paintRankBridge });
  }());

  var OVERLAYS = (function () {
    function top(state) {
      return state.overlays.length ? state.overlays[state.overlays.length - 1] : null;
    }
    function focusable(dialog) {
      var all = dialog.querySelectorAll('button:not([disabled]),a[href]:not([hidden]),[tabindex]:not([tabindex="-1"]):not([hidden])');
      var visible = [];
      for (var index = 0; index < all.length; index += 1) {
        if (!all[index].hidden && !all[index].closest("[hidden]")) {
          visible.push(all[index]);
        }
      }
      return visible;
    }
    function selectTab(dialog, tab) {
      var tabs = dialog.querySelectorAll("[data-evidence-tab]");
      var panels = dialog.querySelectorAll("[data-evidence-panel]");
      for (var index = 0; index < tabs.length; index += 1) {
        var selected = tabs[index].getAttribute("data-evidence-tab") === tab;
        tabs[index].setAttribute("aria-selected", selected ? "true" : "false");
        tabs[index].setAttribute("tabindex", selected ? "0" : "-1");
      }
      for (var panelIndex = 0; panelIndex < panels.length; panelIndex += 1) {
        panels[panelIndex].hidden = panels[panelIndex].getAttribute("data-evidence-panel") !== tab;
      }
    }
    function render(state, deck, domById, overlayState) {
      var activeOverlay = top(state);
      for (var index = 0; index < deck.slides.length; index += 1) {
        var slide = deck.slides[index];
        if (slide.runtime) {
          var dom = domById.get(slide.id);
          var evidenceOverlay = null;
          for (var evidenceIndex = 0; evidenceIndex < state.overlays.length; evidenceIndex += 1) {
            if (state.overlays[evidenceIndex].kind === "evidence" && state.overlays[evidenceIndex].ordinal === slide.ordinal) {
              evidenceOverlay = state.overlays[evidenceIndex];
            }
          }
          var open = evidenceOverlay !== null;
          dom.evidence.setAttribute("aria-expanded", open ? "true" : "false");
          dom.dialog.hidden = !open;
          dom.dialog.inert = open && activeOverlay !== evidenceOverlay;
          if (open) {
            selectTab(dom.dialog, evidenceOverlay.tab);
          }
        }
      }
      var overview = document.getElementById("idrt-presenter-overview");
      var help = document.getElementById("idrt-presenter-help");
      invariant(overview && help, "E_PRESENTER_DOM");
      var overviewOpen = false;
      var helpOpen = false;
      for (var overlayIndex = 0; overlayIndex < state.overlays.length; overlayIndex += 1) {
        overviewOpen = overviewOpen || state.overlays[overlayIndex].kind === "overview";
        helpOpen = helpOpen || state.overlays[overlayIndex].kind === "help";
      }
      overview.hidden = !overviewOpen;
      help.hidden = !helpOpen;
      overview.inert = overviewOpen && activeOverlay.kind !== "overview";
      help.inert = helpOpen && activeOverlay.kind !== "help";
      var main = document.getElementById("idrt-deck-pages");
      var chrome = document.getElementById("idrt-presenter-chrome");
      if (activeOverlay) {
        main.inert = true;
        chrome.inert = true;
        var token = String(state.overlays.length) + ":" + activeOverlay.kind;
        if (overlayState.token !== token) {
          overlayState.token = token;
          var dialog = activeOverlay.kind === "evidence" ? domById.get(deck.slides[state.currentIndex].id).dialog : activeOverlay.kind === "overview" ? overview : help;
          var close = dialog.querySelector(activeOverlay.kind === "evidence" ? '[data-action="evidence-close"]' : '[data-presenter-close]');
          invariant(close, "E_PRESENTER_DOM");
          close.focus();
        }
      } else {
        main.inert = false;
        chrome.inert = false;
        overlayState.token = null;
      }
    }
    function trap(event, dialog) {
      if (event.key !== "Tab") {
        return false;
      }
      var targets = focusable(dialog);
      if (!targets.length) {
        event.preventDefault();
        return true;
      }
      var first = targets[0];
      var last = targets[targets.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
        return true;
      }
      if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
        return true;
      }
      return false;
    }
    return Object.freeze({ render: render, trap: trap });
  }());

  var NAVIGATION = (function () {
    var WIDGET_ROLES = new Set(["application", "button", "checkbox", "combobox", "dialog", "feed", "grid", "gridcell", "link", "listbox", "menu", "menubar", "menuitem", "menuitemcheckbox", "menuitemradio", "option", "progressbar", "radio", "radiogroup", "scrollbar", "searchbox", "separator", "slider", "spinbutton", "switch", "tab", "tablist", "textbox", "toolbar", "tree", "treegrid", "treeitem"]);
    function interactiveTarget(target) {
      var node = target && target.nodeType === 1 ? target : target && target.parentElement;
      while (node && node.nodeType === 1) {
        if (node.matches && node.matches("button,a[href],input,textarea,select,option,summary")) {
          return true;
        }
        if (node.hasAttribute && node.hasAttribute("contenteditable") && String(node.getAttribute("contenteditable") || "true").toLowerCase() !== "false") {
          return true;
        }
        if (node.hasAttribute && node.hasAttribute("tabindex") && node.tabIndex >= 0) {
          return true;
        }
        var roles = String(node.getAttribute && node.getAttribute("role") || "").trim().toLowerCase().split(/\s+/);
        for (var roleIndex = 0; roleIndex < roles.length; roleIndex += 1) {
          if (WIDGET_ROLES.has(roles[roleIndex])) {
            return true;
          }
        }
        node = node.parentElement;
      }
      return false;
    }
    function interactiveEvent(event) {
      var path = event.composedPath ? event.composedPath() : [event.target];
      for (var index = 0; index < path.length; index += 1) {
        if (interactiveTarget(path[index])) {
          return true;
        }
      }
      return false;
    }
    function presenterShortcutTarget(target) {
      var node = target && target.nodeType === 1 ? target : target && target.parentElement;
      while (node && node.nodeType === 1) {
        if (node.matches && node.matches("button,a[href],input,textarea,select,option,summary")) {
          return true;
        }
        if (node.hasAttribute && node.hasAttribute("contenteditable") && String(node.getAttribute("contenteditable") || "true").toLowerCase() !== "false") {
          return true;
        }
        node = node.parentElement;
      }
      return false;
    }
    function interactivePoint(event) {
      return interactiveTarget(document.elementFromPoint(event.clientX, event.clientY));
    }
    function install(controller, deck, scheduler) {
      var chrome = document.getElementById("idrt-presenter-chrome");
      var pageLinks = chrome.querySelectorAll("[data-page-index]");
      var previousLink = chrome.querySelector('[data-nav-action="previous"]');
      var nextLink = chrome.querySelector('[data-nav-action="next"]');
      invariant(previousLink && nextLink && pageLinks.length === deck.slides.length, "E_NAV_DOM");
      var idleTimer = null;
      function wake() {
        chrome.classList.remove("is-idle");
        if (idleTimer !== null) {
          scheduler.clearTimeout(idleTimer);
        }
        idleTimer = scheduler.setTimeout(function () {
          controller.guard(0, "E_NAV_TIMER", function () {
            if (!chrome.contains(document.activeElement)) {
              chrome.classList.add("is-idle");
            }
          });
        }, 2500);
      }
      for (var index = 0; index < pageLinks.length; index += 1) {
        (function (targetIndex) {
          pageLinks[targetIndex].addEventListener("click", function (event) {
            controller.guard(0, "E_NAV_CLICK", function () {
              event.preventDefault();
              controller.navigate(targetIndex, false);
              wake();
            });
          });
        }(index));
      }
      previousLink.addEventListener("click", function (event) {
        controller.guard(0, "E_NAV_CLICK", function () {
          event.preventDefault();
          controller.navigate(controller.currentIndex() - 1, false);
          wake();
        });
      });
      nextLink.addEventListener("click", function (event) {
        controller.guard(0, "E_NAV_CLICK", function () {
          event.preventDefault();
          controller.navigate(controller.currentIndex() + 1, false);
          wake();
        });
      });
      document.addEventListener("keydown", function (event) {
        controller.guard(0, "E_NAV_KEY", function () {
          if (controller.overlayOpen() && event.key === "Escape") {
            event.preventDefault();
            controller.closeOverlay();
            return;
          }
          if (event.isComposing || event.ctrlKey || event.metaKey) {
            return;
          }
          if (event.altKey) {
            if (presenterShortcutTarget(event.target)) {
              return;
            }
            var presenterKey = event.key.toLowerCase();
            if (["o", "r", "d", "f", "h"].indexOf(presenterKey) < 0) {
              return;
            }
            event.preventDefault();
            if (presenterKey === "o") { controller.openPresenter("overview", null); }
            else if (presenterKey === "r") { controller.reset(); }
            else if (presenterKey === "d") { controller.startDemo(event); }
            else if (presenterKey === "f") { controller.toggleFullscreen(); }
            else { controller.openPresenter("help", null); }
            return;
          }
          if (controller.overlayOpen()) {
            var dialog = document.querySelector('.presenter-dialog:not([hidden]):not([inert]),.evidence-dialog:not([hidden]):not([inert])');
            if (dialog) { OVERLAYS.trap(event, dialog); }
            return;
          }
          if (interactiveTarget(event.target)) { return; }
          var current = controller.currentIndex();
          var next = null;
          if (event.key === "ArrowRight" || event.key === "PageDown" || event.key === " ") {
            next = current + 1;
          } else if (event.key === "ArrowLeft" || event.key === "PageUp") {
            next = current - 1;
          } else if (event.key === "Home") {
            next = 0;
          } else if (event.key === "End") {
            next = deck.slides.length - 1;
          }
          if (next !== null) {
            event.preventDefault();
            controller.navigate(next, true);
            wake();
          }
        });
      });
      var pointer = null;
      var activePointers = new Set();
      var suppressClickUntil = 0;
      document.addEventListener("pointerdown", function (event) {
        controller.guard(0, "E_POINTER", function () {
          if (activePointers.size > 0 && !activePointers.has(event.pointerId)) {
            pointer = null;
          }
          activePointers.add(event.pointerId);
        });
      }, { capture: true, passive: true });
      for (var slideIndex = 0; slideIndex < deck.slides.length; slideIndex += 1) {
        (function (pageIndex) {
          var frame = document.getElementById("idrt-page-" + (pageIndex + 1)).querySelector(".frame");
          frame.addEventListener("pointerdown", function (event) {
            controller.guard(pageIndex + 1, "E_POINTER", function () {
              pointer = interactiveEvent(event) || interactivePoint(event) || pointer || activePointers.size > 1 ? null : { id: event.pointerId, page: pageIndex, x: event.clientX, y: event.clientY };
            });
          });
          frame.addEventListener("click", function (event) {
            controller.guard(pageIndex + 1, "E_FRAME_CLICK", function () {
              if (scheduler.now() <= suppressClickUntil) {
                suppressClickUntil = 0;
                event.preventDefault();
                return;
              }
              if (interactiveEvent(event)) {
                return;
              }
              var bounds = frame.getBoundingClientRect();
              var ratio = (event.clientX - bounds.left) / bounds.width;
              if (ratio <= 0.15) {
                controller.navigate(pageIndex - 1, true);
              } else if (ratio >= 0.85) {
                controller.navigate(pageIndex + 1, true);
              }
            });
          });
        }(slideIndex));
      }
      document.addEventListener("pointermove", function (event) {
        controller.guard(0, "E_POINTER", function () {
          if (pointer && (pointer.id !== event.pointerId || interactiveEvent(event) || interactivePoint(event))) {
            pointer = null;
          }
          wake();
        });
      }, { passive: true });
      document.addEventListener("pointercancel", function (event) {
        controller.guard(0, "E_POINTER", function () {
          activePointers.delete(event.pointerId);
          pointer = null;
        });
      }, { passive: true });
      document.addEventListener("pointerup", function (event) {
        controller.guard(0, "E_POINTER", function () {
          var activePointer = pointer;
          pointer = null;
          activePointers.delete(event.pointerId);
          if (!activePointer || activePointer.id !== event.pointerId || interactiveEvent(event) || interactivePoint(event)) {
            return;
          }
          var dx = event.clientX - activePointer.x;
          var dy = event.clientY - activePointer.y;
          if (Math.abs(dx) >= 48 && Math.abs(dx) >= 1.5 * Math.abs(dy)) {
            suppressClickUntil = scheduler.now() + 500;
            controller.navigate(activePointer.page + (dx < 0 ? 1 : -1), true);
          }
        });
      }, { passive: true });
      document.addEventListener("touchstart", function () { controller.guard(0, "E_NAV_WAKE", wake); }, { passive: true });
      chrome.addEventListener("focusin", function () { controller.guard(0, "E_NAV_WAKE", wake); });
      controller.guard(0, "E_NAV_WAKE", wake);
      return function update(index) {
        for (var linkIndex = 0; linkIndex < pageLinks.length; linkIndex += 1) {
          if (linkIndex === index) {
            pageLinks[linkIndex].setAttribute("aria-current", "page");
          } else {
            pageLinks[linkIndex].removeAttribute("aria-current");
          }
        }
        previousLink.setAttribute("href", "#idrt-page-" + String(Math.max(1, index)));
        nextLink.setAttribute("href", "#idrt-page-" + String(Math.min(deck.slides.length, index + 2)));
        previousLink.setAttribute("aria-disabled", index === 0 ? "true" : "false");
        nextLink.setAttribute("aria-disabled", index === deck.slides.length - 1 ? "true" : "false");
      };
    }
    return Object.freeze({ install: install });
  }());

  var CONTROLLER = (function () {
    function create(deck, scheduler) {
      var pages = new Map();
      var printPages = new Map();
      var domById = new Map();
      var animations = new Map();
      var announceTimers = new Map();
      var generation = new Map();
      var renderedGeometry = new Map();
      var panelReturnOpener = null;
      var overlayOpeners = [];
      var activeTooltip = null;
      var overlayState = { token: null };
      var labels = deck.payload.lang === "ja" ? { static: "静的な結論を表示", live: "動的表示に戻る", failure: "動的表示を利用できません。初期状態を表示します。" } : { static: "View static conclusion", live: "Return to live view", failure: "Interactive view unavailable. Static baseline restored." };
      var state;
      var updateNavigation = function () {};
      var pendingHash = null;
      var disposed = false;
      var replayTimer = null;
      var fullscreenGeneration = 0;
      var presenterStatus = document.getElementById("idrt-presenter-status");
      var demoControl = document.querySelector('[data-presenter-action="demo"]');
      var demoCue = document.getElementById("idrt-demo-cue");
      var targetNodes = new Map();
      var demoActive = false;
      var demoGeneration = 0;
      var demoTimers = new Set();
      var demoTouchedOrdinals = new Set();
      var demoAdvanceOrdinal = null;
      var suppressedDemoEvent = null;
      var suppressDemoClick = false;
      var startDemoOnReady = window.location.hash === "#demo";
      invariant(presenterStatus && demoControl && demoCue, "E_PRESENTER_DOM");

      for (var index = 0; index < deck.slides.length; index += 1) {
        var slide = deck.slides[index];
        var dom = VIEW.nodes(slide);
        domById.set(slide.id, dom);
        if (slide.runtime) {
          var inputs = new Map();
          if (slide.runtime.scene.type === "evidence_only") {
            inputs.set("evidence", slide.runtime.scene.initialState.evidence);
          } else if (slide.runtime.scene.type === "drilldown" || slide.runtime.scene.type === "accordion") {
            inputs.set("panel", slide.runtime.scene.initialState.panel);
          } else {
            for (var controlIndex = 0; controlIndex < slide.runtime.controlList.length; controlIndex += 1) {
              var control = slide.runtime.controlList[controlIndex];
              var initialValue = slide.runtime.scene.initialState[control.id];
              inputs.set(control.id, control.kind === "range" ? DECIMAL.parse(initialValue, slide.runtime.scene.scale) : initialValue);
            }
          }
          var evaluation = MODEL.evaluate(slide.runtime, inputs, "initial", null);
          MODEL.matchesInitial(slide.runtime, evaluation);
          var initialPage = Object.freeze({ inputs: inputs, evaluation: evaluation, viewMode: "live", failed: null });
          pages.set(slide.id, initialPage);
          printPages.set(slide.id, initialPage);
        } else {
          pages.set(slide.id, null);
          printPages.set(slide.id, null);
        }
      }
      var declaredTargetCount = 0;
      var targetElements = document.querySelectorAll("[data-target-slide][data-target-key]");
      for (var targetElementIndex = 0; targetElementIndex < targetElements.length; targetElementIndex += 1) {
        var targetElement = targetElements[targetElementIndex];
        var targetSlideId = targetElement.getAttribute("data-target-slide");
        var targetKey = targetElement.getAttribute("data-target-key");
        var targetSlide = null;
        for (var targetSlideIndex = 0; targetSlideIndex < deck.slides.length; targetSlideIndex += 1) {
          if (deck.slides[targetSlideIndex].id === targetSlideId) { targetSlide = deck.slides[targetSlideIndex]; }
        }
        invariant(targetSlide && targetSlide.runtime && targetSlide.runtime.targets.has(targetKey), "E_TARGET_DOM");
        if (!targetNodes.has(targetSlideId)) { targetNodes.set(targetSlideId, new Map()); }
        invariant(!targetNodes.get(targetSlideId).has(targetKey), "E_TARGET_DOM");
        targetNodes.get(targetSlideId).set(targetKey, targetElement);
      }
      for (var declaredSlideIndex = 0; declaredSlideIndex < deck.slides.length; declaredSlideIndex += 1) {
        var declaredSlide = deck.slides[declaredSlideIndex];
        if (!declaredSlide.runtime) { continue; }
        declaredSlide.runtime.targets.forEach(function (_target, declaredKey) {
          declaredTargetCount += 1;
          invariant(targetNodes.has(declaredSlide.id) && targetNodes.get(declaredSlide.id).has(declaredKey), "E_TARGET_DOM");
        });
      }
      invariant(targetElements.length === declaredTargetCount, "E_TARGET_DOM");
      var media = window.matchMedia("(prefers-reduced-motion: reduce)");
      state = Object.freeze({ currentIndex: 0, pages: pages, overlays: Object.freeze([]), reducedMotion: media.matches });

      function cancelOrdinal(ordinal) {
        var frame = animations.get(ordinal);
        if (frame !== undefined) {
          scheduler.cancelAnimationFrame(frame);
          animations.delete(ordinal);
        }
        var announce = announceTimers.get(ordinal);
        if (announce !== undefined) {
          scheduler.clearTimeout(announce);
          announceTimers.delete(ordinal);
        }
        generation.set(ordinal, (generation.get(ordinal) || 0) + 1);
      }

      function dispose() {
        if (disposed) {
          return;
        }
        disposed = true;
        demoGeneration += 1;
        demoActive = false;
        demoTimers.forEach(function (handle) { scheduler.clearTimeout(handle); });
        demoTimers.clear();
        demoTouchedOrdinals.clear();
        try { hideDemoCue(); } catch (ignoredDemoCue) {}
        if (replayTimer !== null) {
          scheduler.clearTimeout(replayTimer);
          replayTimer = null;
        }
        fullscreenGeneration += 1;
        for (var index = 0; index < deck.slides.length; index += 1) {
          try {
            cancelOrdinal(deck.slides[index].ordinal);
          } catch (ignoredCancellation) {
            generation.set(deck.slides[index].ordinal, (generation.get(deck.slides[index].ordinal) || 0) + 1);
          }
        }
      }

      function failScene(ordinal, code) {
        if (disposed) {
          return;
        }
        if (!Number.isInteger(ordinal) || ordinal < 1 || ordinal > deck.slides.length) {
          ordinal = state.currentIndex + 1;
        }
        var slide = deck.slides[ordinal - 1];
        if (!slide || !slide.runtime) {
          return;
        }
        var page = state.pages.get(slide.id);
        if (page && page.failed) {
          return;
        }
        var wasActive = state.currentIndex === ordinal - 1;
        cancelOrdinal(ordinal);

        var dom = domById.get(slide.id);
        if (dom) {
          try { closeTooltip(false); } catch (ignoredTooltipClose) {}
          try {
            var failClosedControls = dom.section.querySelectorAll("input, select, button");
            for (var failControlIndex = 0; failControlIndex < failClosedControls.length; failControlIndex += 1) {
              failClosedControls[failControlIndex].disabled = true;
              failClosedControls[failControlIndex].setAttribute("aria-disabled", "true");
            }
          } catch (ignoredFailClosedControls) {}
          try { dom.status.setAttribute("aria-live", "polite"); } catch (ignoredLiveRegion) {}
          try {
            dom.section.setAttribute("data-runtime", "failed");
            dom.section.setAttribute("data-error-code", code);
          } catch (ignoredMarker) {
            /* The remaining fallbacks still run when even marker writes fail. */
          }
          try {
            dom.fallback.hidden = false;
            dom.live.hidden = true;
            dom.rail.hidden = false;
            dom.dialog.hidden = true;
          } catch (ignoredVisibility) {
            /* Each following safety operation is independent. */
          }
          try {
            dom.staticSummary.hidden = false;
            dom.staticSummary.removeAttribute("aria-hidden");
          } catch (ignoredStaticSummary) {}
          try {
            dom.liveSummary.hidden = true;
            dom.liveSummary.setAttribute("aria-hidden", "true");
          } catch (ignoredLiveSummary) {}
          try { dom.input.disabled = true; } catch (ignoredInput) {}
          try { dom.reset.disabled = true; } catch (ignoredReset) {}
          try { dom.evidence.disabled = true; } catch (ignoredEvidence) {}
          try { dom.evidence.setAttribute("aria-expanded", "false"); } catch (ignoredEvidenceState) {}
          try { dom.toggle.disabled = true; } catch (ignoredToggle) {}
        }

        try {
          var originalIndex = state.currentIndex;
          if (originalIndex !== ordinal - 1) {
            state = Object.freeze({ currentIndex: ordinal - 1, pages: state.pages, overlays: Object.freeze([]), reducedMotion: state.reducedMotion });
          }
          state = STATE.reduce(state, { type: "FAIL_SCENE", code: code }, deck);
          if (originalIndex !== ordinal - 1) {
            state = Object.freeze({ currentIndex: originalIndex, pages: state.pages, overlays: Object.freeze([]), reducedMotion: state.reducedMotion });
          }
        } catch (ignoredState) {}

        if (dom) {
          try { VIEW.baseline(slide, page, dom, labels, printPages.get(slide.id)); } catch (ignoredBaseline) {}
          try {
            dom.fallback.hidden = false;
            dom.live.hidden = true;
            dom.rail.hidden = false;
            dom.dialog.hidden = true;
          } catch (ignoredFinalVisibility) {}
          try { dom.input.disabled = true; } catch (ignoredFinalInput) {}
          try { dom.reset.disabled = true; } catch (ignoredFinalReset) {}
          try { dom.evidence.disabled = true; } catch (ignoredFinalEvidence) {}
          try { dom.toggle.disabled = true; } catch (ignoredFinalToggle) {}
          try { dom.status.textContent = labels.failure; } catch (ignoredStatus) {}
        }
        try { document.getElementById("idrt-deck-pages").inert = false; } catch (ignoredMainInert) {}
        try { document.getElementById("idrt-presenter-chrome").inert = false; } catch (ignoredChromeInert) {}
        panelReturnOpener = null;
        overlayOpeners = [];
        overlayState.token = null;
        if (wasActive && dom) {
          try { dom.heading.focus(); } catch (ignoredFocus) {}
        }
        console.error("[interactive-deck] page-" + ordinal + " " + code + ": Interactive scene unavailable.");
      }

      function failAllScenes(code) {
        for (var index = 0; index < deck.slides.length; index += 1) {
          if (deck.slides[index].runtime) {
            failScene(index + 1, code);
          }
        }
      }

      function guard(ordinal, code, operation) {
        if (disposed) {
          return undefined;
        }
        try {
          return operation();
        } catch (failure) {
          if (ordinal === 0) {
            failAllScenes(code);
          } else {
            failScene(ordinal, code);
          }
          return undefined;
        }
      }

      function snapshot() {
        var records = [];
        for (var index = 0; index < deck.slides.length; index += 1) {
          var slide = deck.slides[index];
          var page = state.pages.get(slide.id);
          var inputs = {};
          var outputs = {};
          var outcome = null;
          if (slide.runtime && page) {
            var snapshotControls = slide.runtime.controlList || [];
            for (var controlIndex = 0; controlIndex < snapshotControls.length; controlIndex += 1) {
              var snapshotControl = snapshotControls[controlIndex];
              if (snapshotControl.kind === "range") {
                inputs[snapshotControl.id] = DECIMAL.canonical(page.inputs.get(snapshotControl.id), slide.runtime.scene.scale);
              }
            }
            slide.runtime.definitions.forEach(function (definition, outputId) {
              var outputValue = page.evaluation.outputs.get(outputId);
              if (definition.kind === "numeric" && typeof outputValue === "bigint") { outputs[outputId] = DECIMAL.canonical(outputValue, slide.runtime.scene.scale); }
            });
            outcome = page.evaluation.decision ? page.evaluation.decision.outcome : null;
          }
          records.push(Object.freeze({ ordinal: slide.ordinal, inputs: Object.freeze(inputs), outputs: Object.freeze(outputs), outcome: outcome, viewMode: slide.runtime && page ? page.viewMode : "static", failed: slide.runtime && page && page.failed ? "unavailable" : null }));
        }
        var evidenceOverlay = null;
        for (var overlayIndex = state.overlays.length - 1; overlayIndex >= 0; overlayIndex -= 1) {
          if (state.overlays[overlayIndex].kind === "evidence") { evidenceOverlay = state.overlays[overlayIndex]; break; }
        }
        var overlay = evidenceOverlay ? Object.freeze({ kind: evidenceOverlay.kind, ordinal: evidenceOverlay.ordinal, tab: evidenceOverlay.tab }) : null;
        return Object.freeze({ currentSlide: state.currentIndex + 1, pages: Object.freeze(records), overlay: overlay, reducedMotion: state.reducedMotion });
      }
      function emit(name) {
        document.dispatchEvent(new CustomEvent(name, { detail: snapshot() }));
      }
      function writeUrl() {
        var target = URL_STATE.serialize(state, deck);
        try {
          history.replaceState(null, "", window.location.pathname + window.location.search + target);
        } catch (ignoredHistoryRestriction) {
          try {
            if (window.location.hash !== target) {
              pendingHash = target;
              window.location.hash = target;
            }
          } catch (ignoredHashFallback) {
            pendingHash = null;
            /* A fully restricted location still must not disable the scene. */
          }
        }
      }
      function prepareAnnouncement(slide, dom) {
        var prior = announceTimers.get(slide.ordinal);
        if (prior !== undefined) {
          scheduler.clearTimeout(prior);
          announceTimers.delete(slide.ordinal);
        }
        dom.status.setAttribute("aria-live", "off");
      }
      function announce(slide, dom) {
        var token = generation.get(slide.ordinal) || 0;
        announceTimers.set(slide.ordinal, scheduler.setTimeout(function () {
          guard(slide.ordinal, "E_STATUS_TIMER", function () {
            if ((generation.get(slide.ordinal) || 0) !== token) {
              return;
            }
            dom.status.setAttribute("aria-live", "polite");
            var sentence = dom.status.textContent;
            dom.status.textContent = "";
            dom.status.textContent = sentence;
            announceTimers.delete(slide.ordinal);
          });
        }, 180));
      }
      function paintGeometry(slide, points, positions) {
        VIEW.paint(points, positions);
        var stored = [];
        for (var index = 0; index < positions.length; index += 1) {
          stored.push(Object.freeze({ id: points[index].id, x: positions[index].x, y: positions[index].y }));
        }
        renderedGeometry.set(slide.ordinal, Object.freeze(stored));
      }
      function pointWithId(points, id) {
        for (var pointIndex = 0; pointIndex < points.length; pointIndex += 1) {
          if (points[pointIndex].id === id) { return points[pointIndex]; }
        }
        return null;
      }
      function animate(slide, page, previous) {
        if (domById.get(slide.id).section.getAttribute("data-visual-layout") === "rank_bridge") {
          cancelOrdinal(slide.ordinal);
          if (state.reducedMotion || !previous || page.viewMode === "static") {
            VIEW.paintBridge(slide, page);
            renderedGeometry.set(slide.ordinal, page.evaluation.view.items.map(function (item) { return {id: item.id, x: 0, y: item.rank}; }));
            return;
          }
          var bridgeToken = generation.get(slide.ordinal) || 0;
          var bridgeStart = scheduler.now();
          var previousItems = previous.evaluation.view.items;
          var lastRanks = renderedGeometry.get(slide.ordinal);
          function bridgeFrame(now) {
            guard(slide.ordinal, "E_ANIMATION_FRAME", function () {
              if ((generation.get(slide.ordinal) || 0) !== bridgeToken) { return; }
              var progress = Math.max(0, Math.min(1, (now - bridgeStart) / 240));
              var ease = 1 - Math.pow(1 - progress, 3);
              var ranks = new Map();
              page.evaluation.view.items.forEach(function (item) {
                var old = previousItems.find(function (candidate) { return candidate.id === item.id; });
                var rendered = lastRanks && pointWithId(lastRanks, item.id);
                var startRank = rendered ? rendered.y : old.rank;
                ranks.set(item.id, startRank + (item.rank - startRank) * ease);
              });
              VIEW.paintBridge(slide, page, ranks);
              renderedGeometry.set(slide.ordinal, page.evaluation.view.items.map(function (item) { return {id: item.id, x: 0, y: ranks.get(item.id)}; }));
              if (progress < 1) { animations.set(slide.ordinal, scheduler.requestAnimationFrame(bridgeFrame)); }
              else { animations.delete(slide.ordinal); }
            });
          }
          bridgeFrame(bridgeStart);
          return;
        }
        var points = VIEW.geometry(slide, page.evaluation);
        var target = [];
        var start = [];
        var rendered = renderedGeometry.get(slide.ordinal);
        for (var index = 0; index < points.length; index += 1) {
          target.push({ x: points[index].x, y: points[index].y });
          var oldPoint = rendered && rendered.length === points.length ? pointWithId(rendered, points[index].id) : previous ? pointWithId(previous.evaluation.points, points[index].id) : pointWithId(page.evaluation.points, points[index].id);
          invariant(oldPoint, "E_DOM_GEOMETRY");
          start.push({ x: oldPoint.x, y: oldPoint.y });
        }
        cancelOrdinal(slide.ordinal);
        var token = generation.get(slide.ordinal) || 0;
        if (state.reducedMotion || !previous || page.viewMode === "static") {
          paintGeometry(slide, points, target);
          return;
        }
        var began = scheduler.now();
        function frame(now) {
          guard(slide.ordinal, "E_ANIMATION_FRAME", function () {
            if ((generation.get(slide.ordinal) || 0) !== token) {
              return;
            }
            var fraction = Math.max(0, Math.min(1, (now - began) / 240));
            var eased = 1 - Math.pow(1 - fraction, 3);
            var positions = [];
            for (var index = 0; index < target.length; index += 1) {
              positions.push({ x: start[index].x + (target[index].x - start[index].x) * eased, y: start[index].y + (target[index].y - start[index].y) * eased });
            }
            paintGeometry(slide, points, positions);
            if (fraction < 1) {
              animations.set(slide.ordinal, scheduler.requestAnimationFrame(frame));
            } else {
              animations.delete(slide.ordinal);
            }
          });
        }
        animations.set(slide.ordinal, scheduler.requestAnimationFrame(frame));
      }
      function fitLiveViewports() {
        var compact = window.matchMedia("(max-width: 760px), (orientation: portrait)").matches;
        deck.slides.forEach(function (slide) {
          if (!slide.runtime || ["slider_model", "score_model", "state_toggle"].indexOf(slide.runtime.scene.type) < 0) { return; }
          var svg = domById.get(slide.id).live.querySelector("svg");
          if (svg) {
            var bridge = domById.get(slide.id).section.getAttribute("data-visual-layout") === "rank_bridge";
            var viewport = compact ? (bridge ? "0 170 390 440" : "60 190 790 440") : "0 0 1280 720";
            var changed = svg.getAttribute("viewBox") !== viewport;
            svg.setAttribute("viewBox", viewport);
            if (bridge && changed) {
              cancelOrdinal(slide.ordinal);
              var bridgePage = state.pages.get(slide.id);
              VIEW.paintBridge(slide, bridgePage);
              renderedGeometry.set(slide.ordinal, bridgePage.evaluation.view.items.map(function (item) { return {id: item.id, x: 0, y: item.rank}; }));
            }
          }
        });
      }
      function render(previousState, options) {
        for (var index = 0; index < deck.slides.length; index += 1) {
          var slide = deck.slides[index];
          var dom = domById.get(slide.id);
          var active = index === state.currentIndex;
          dom.section.hidden = !active;
          dom.section.inert = !active;
          if (slide.runtime) {
            var page = state.pages.get(slide.id);
            var previous = previousState ? previousState.pages.get(slide.id) : null;
            if (active && options && options.announce) {
              prepareAnnouncement(slide, dom);
            }
            VIEW.semantic(slide, page, dom, labels, printPages.get(slide.id));
            if (!page.failed) {
              dom.section.setAttribute("data-runtime", "ready");
              if (page.viewMode === "live") {
                var skipRankMotion = dom.section.getAttribute("data-visual-layout") === "rank_bridge" && options && options.animate === false;
                animate(slide, page, !skipRankMotion && previous && previous.evaluation !== page.evaluation ? previous : null);
              }
            }
            if (active && options && options.announce) {
              announce(slide, dom);
            }
          }
        }
        OVERLAYS.render(state, deck, domById, overlayState);
        fitLiveViewports();
        updateNavigation(state.currentIndex);
      }
      function dispatch(action, options) {
        var previous = state;
        var candidate = STATE.reduce(state, action, deck);
        state = candidate;
        try {
          render(previous, options || {});
        } catch (failure) {
          state = previous;
          throw failure;
        }
        if (!options || options.url !== false) {
          writeUrl();
        }
        emit("deck:state");
      }
      function navigate(index, focusHeading) {
        var bounded = Math.max(0, Math.min(deck.slides.length - 1, index));
        cancelOrdinal(deck.slides[state.currentIndex].ordinal);
        if (bounded !== state.currentIndex) {
          closeTooltip(false);
        }
        overlayOpeners = [];
        dispatch({ type: "NAVIGATE", index: bounded }, { announce: false });
        if (focusHeading) {
          domById.get(deck.slides[bounded].id).heading.focus();
        }
      }
      function closeOverlay() {
        if (!state.overlays.length) {
          return;
        }
        var closing = state.overlays[state.overlays.length - 1];
        var declaredEvidenceState = closing.kind === "evidence" && deck.slides[state.currentIndex].runtime && deck.slides[state.currentIndex].runtime.scene.type === "evidence_only";
        var overlayOpener = overlayOpeners.length ? overlayOpeners.pop() : null;
        dispatch({ type: "CLOSE_TOP_OVERLAY" }, { announce: declaredEvidenceState, url: declaredEvidenceState });
        if (overlayOpener && document.contains(overlayOpener) && !overlayOpener.closest("[hidden]") && !overlayOpener.closest("[inert]")) {
          overlayOpener.focus();
        } else if (state.overlays.length) {
          var openDialog = document.querySelector('.presenter-dialog:not([hidden]),.evidence-dialog:not([hidden])');
          var closeButton = openDialog && openDialog.querySelector('[data-presenter-close],[data-action="evidence-close"]');
          if (closeButton) { closeButton.focus(); }
        } else {
          domById.get(deck.slides[state.currentIndex].id).heading.focus();
        }
      }
      function openPresenterOverlay(kind, source) {
        var presenterOpener = source || document.querySelector('[data-presenter-action="' + kind + '"]');
        invariant(presenterOpener, "E_PRESENTER_DOM");
        overlayOpeners.push(presenterOpener);
        dispatch({ type: "OPEN_PRESENTER_OVERLAY", kind: kind }, { announce: false, url: false });
      }
      function clearOverlays() {
        overlayOpeners = [];
        if (state.overlays.length) {
          dispatch({ type: "CLEAR_OVERLAYS" }, { announce: false, url: false });
        }
      }
      function replayCurrent() {
        clearOverlays();
        var slide = deck.slides[state.currentIndex];
        if (slide.runtime) {
          dispatch({ type: "RESET_PAGE" }, { announce: true });
        }
        var section = domById.get(slide.id).section;
        section.classList.remove("is-replaying");
        if (replayTimer !== null) { scheduler.clearTimeout(replayTimer); }
        if (!state.reducedMotion) {
          section.classList.add("is-replaying");
          replayTimer = scheduler.setTimeout(function () {
            guard(slide.ordinal, "E_REPLAY_TIMER", function () {
              section.classList.remove("is-replaying");
              replayTimer = null;
            });
          }, 360);
        }
      }
      function setLocalFullscreen(active) {
        var root = document.documentElement;
        var control = document.querySelector('[data-presenter-action="fullscreen"]');
        root.classList.toggle("idrt-local-fullscreen", active);
        if (active) { root.setAttribute("data-fullscreen-mode", "local"); }
        else if (root.getAttribute("data-fullscreen-mode") === "local") { root.removeAttribute("data-fullscreen-mode"); }
        if (control) { control.setAttribute("aria-pressed", active || Boolean(document.fullscreenElement) ? "true" : "false"); }
      }
      function toggleFullscreen() {
        fullscreenGeneration += 1;
        var token = fullscreenGeneration;
        var root = document.documentElement;
        if (root.classList.contains("idrt-local-fullscreen")) {
          setLocalFullscreen(false);
          return;
        }
        if (document.fullscreenElement) {
          try {
            var exitResult = document.exitFullscreen();
            if (exitResult && typeof exitResult.catch === "function") { exitResult.catch(function () {}); }
          } catch (ignoredFullscreenExit) {}
          return;
        }
        if (typeof root.requestFullscreen !== "function") {
          setLocalFullscreen(true);
          return;
        }
        try {
          var request = root.requestFullscreen();
          if (request && typeof request.then === "function") {
            request.then(function () {
              if (token === fullscreenGeneration) { setLocalFullscreen(false); }
            }, function () {
              if (token === fullscreenGeneration) { setLocalFullscreen(true); }
            });
          } else if (!document.fullscreenElement) { setLocalFullscreen(true); }
        } catch (ignoredFullscreenRequest) {
          if (token === fullscreenGeneration) { setLocalFullscreen(true); }
        }
      }
      function hideDemoCue() {
        demoCue.hidden = true;
        demoCue.classList.remove("is-positioning");
        demoCue.classList.remove("is-static");
        demoCue.removeAttribute("data-slide-id");
        demoCue.removeAttribute("data-target-key");
        demoCue.style.left = "";
        demoCue.style.top = "";
        demoCue.style.width = "";
        demoCue.style.height = "";
      }
      function rectanglesOverlap(first, second) {
        return first.left < second.right && first.right > second.left && first.top < second.bottom && first.bottom > second.top;
      }
      function positionDemoCue(slide, targetKey, hideIfUnavailable) {
        invariant(targetNodes.has(slide.id) && targetNodes.get(slide.id).has(targetKey), "E_DEMO_TARGET");
        var target = targetNodes.get(slide.id).get(targetKey);
        if (target.hidden || target.closest("[hidden]") || target.closest("[inert]")) {
          if (hideIfUnavailable) { hideDemoCue(); return false; }
          invariant(false, "E_DEMO_TARGET");
        }
        var previousCue = demoCue.hidden ? null : demoCue.getBoundingClientRect();
        if (!hideIfUnavailable) { target.scrollIntoView({ block: "center", inline: "center", behavior: "auto" }); }
        var bounds = target.getBoundingClientRect();
        if (bounds.width < 12 || bounds.height < 12) {
          if (hideIfUnavailable) { hideDemoCue(); return false; }
          invariant(false, "E_DEMO_TARGET");
        }
        var size = Math.max(10, Math.min(22, bounds.width - 4, bounds.height - 4));
        var leftMinimum = Math.max(2, bounds.left + 2);
        var leftMaximum = Math.min(window.innerWidth - size - 2, bounds.right - size - 2);
        var topMinimum = Math.max(2, bounds.top + 2);
        var topMaximum = Math.min(window.innerHeight - size - 2, bounds.bottom - size - 2);
        if (leftMaximum < leftMinimum || topMaximum < topMinimum) {
          if (hideIfUnavailable) { hideDemoCue(); return false; }
          invariant(false, "E_DEMO_TARGET");
        }
        var horizontal = [leftMinimum, (leftMinimum + leftMaximum) / 2, leftMaximum];
        var vertical = [topMinimum, (topMinimum + topMaximum) / 2, topMaximum];
        var protectedNodes = document.querySelectorAll("h1,[data-live-value],.derived-tooltip:not([hidden]),.evidence-card p,.evidence-card li,.evidence-card h2,.evidence-card h3");
        function cueCandidate(left, top, candidateSize) {
          return { left: left, top: top, right: left + candidateSize, bottom: top + candidateSize };
        }
        function candidateBlocked(candidate) {
          for (var protectedIndex = 0; protectedIndex < protectedNodes.length; protectedIndex += 1) {
            var protectedNode = protectedNodes[protectedIndex];
            if (protectedNode.hidden || protectedNode.closest("[hidden]")) { continue; }
            if (rectanglesOverlap(candidate, protectedNode.getBoundingClientRect())) { return true; }
          }
          return false;
        }
        var selected = null;
        for (var verticalIndex = 0; verticalIndex < vertical.length && selected === null; verticalIndex += 1) {
          for (var horizontalIndex = 0; horizontalIndex < horizontal.length && selected === null; horizontalIndex += 1) {
            var candidate = cueCandidate(horizontal[horizontalIndex], vertical[verticalIndex], size);
            if (!candidateBlocked(candidate)) { selected = candidate; }
          }
        }
        if (selected === null) {
          if (hideIfUnavailable) { hideDemoCue(); return false; }
          invariant(false, "E_DEMO_CUE_PLACEMENT");
        }
        var cueTravelLimit = 12;
        var cueSizeTravel = 2;
        var startSize = Math.max(8, size - cueSizeTravel);
        var startLeftMaximum = Math.min(window.innerWidth - startSize - 2, bounds.right - startSize - 2);
        var startTopMaximum = Math.min(window.innerHeight - startSize - 2, bounds.bottom - startSize - 2);
        var horizontalDirection = previousCue && previousCue.left < selected.left ? -1 : 1;
        var verticalDirection = previousCue && previousCue.top < selected.top ? -1 : 1;
        var startOffsets = [
          [10 * horizontalDirection, 0], [-10 * horizontalDirection, 0],
          [0, 10 * verticalDirection], [0, -10 * verticalDirection]
        ];
        var startCandidate = null;
        for (var startIndex = 0; startIndex < startOffsets.length && startCandidate === null; startIndex += 1) {
          var startLeft = Math.max(leftMinimum, Math.min(startLeftMaximum, selected.left + startOffsets[startIndex][0]));
          var startTop = Math.max(topMinimum, Math.min(startTopMaximum, selected.top + startOffsets[startIndex][1]));
          var possibleStart = cueCandidate(startLeft, startTop, startSize);
          var centerDeltaX = startLeft + startSize / 2 - (selected.left + size / 2);
          var centerDeltaY = startTop + startSize / 2 - (selected.top + size / 2);
          var centerDistance = Math.sqrt(centerDeltaX * centerDeltaX + centerDeltaY * centerDeltaY);
          if (centerDistance >= 6 && centerDistance <= cueTravelLimit && !candidateBlocked(possibleStart)) {
            startCandidate = possibleStart;
          }
        }
        if (startCandidate === null) {
          startCandidate = cueCandidate(selected.left, selected.top, startSize);
          invariant(!candidateBlocked(startCandidate), "E_DEMO_CUE_PLACEMENT");
        }
        demoCue.setAttribute("data-slide-id", slide.id);
        demoCue.setAttribute("data-target-key", targetKey);
        demoCue.classList.toggle("is-static", state.reducedMotion);
        demoCue.classList.add("is-positioning");
        demoCue.style.left = startCandidate.left.toFixed(1) + "px";
        demoCue.style.top = startCandidate.top.toFixed(1) + "px";
        demoCue.style.width = startSize.toFixed(1) + "px";
        demoCue.style.height = startSize.toFixed(1) + "px";
        demoCue.hidden = false;
        demoCue.getBoundingClientRect();
        demoCue.classList.remove("is-positioning");
        demoCue.style.left = selected.left.toFixed(1) + "px";
        demoCue.style.top = selected.top.toFixed(1) + "px";
        demoCue.style.width = size.toFixed(1) + "px";
        demoCue.style.height = size.toFixed(1) + "px";
        return true;
      }
      function demoEvent(name, detail) {
        document.dispatchEvent(new CustomEvent(name, { detail: Object.freeze(detail) }));
      }
      function demoEndDetail(reason) {
        var slide = deck.slides[state.currentIndex];
        return { reason: reason, slideId: slide.id, ordinal: slide.ordinal };
      }
      function demoStatus(reason) {
        var slide = deck.slides[state.currentIndex];
        var headline = domById.get(slide.id).heading.textContent;
        if (deck.payload.lang === "ja") {
          presenterStatus.textContent = (reason === "complete" ? "デモが完了しました" : "デモを中止しました") + " · スライド" + slide.ordinal + ": " + headline;
        } else {
          presenterStatus.textContent = (reason === "complete" ? "Demo complete" : "Demo cancelled") + " · Slide " + slide.ordinal + ": " + headline;
        }
      }
      function clearDemoTimers() {
        demoTimers.forEach(function (handle) { scheduler.clearTimeout(handle); });
        demoTimers.clear();
      }
      function guardDemoAdvance(operation) {
        var fallbackOrdinal = state.currentIndex + 1;
        demoAdvanceOrdinal = null;
        try {
          return operation();
        } catch (failure) {
          var failedOrdinal = demoAdvanceOrdinal || fallbackOrdinal;
          demoGeneration += 1;
          demoActive = false;
          demoControl.setAttribute("aria-pressed", "false");
          clearDemoTimers();
          demoTouchedOrdinals.forEach(function (ordinal) {
            try {
              cancelOrdinal(ordinal);
            } catch (ignoredDemoCancellation) {
              animations.delete(ordinal);
              announceTimers.delete(ordinal);
              generation.set(ordinal, (generation.get(ordinal) || 0) + 1);
            }
            renderedGeometry.delete(ordinal);
          });
          demoTouchedOrdinals.clear();
          hideDemoCue();
          failScene(failedOrdinal, "E_DEMO_ADVANCE");
          return undefined;
        } finally {
          demoAdvanceOrdinal = null;
        }
      }
      function scheduleDemo(callback, delay, token) {
        var record = { fired: false, handle: null };
        record.handle = scheduler.setTimeout(function () {
          record.fired = true;
          if (record.handle !== null) { demoTimers.delete(record.handle); }
          if (demoActive && token === demoGeneration) { guardDemoAdvance(callback); }
        }, delay);
        if (!record.fired) { demoTimers.add(record.handle); }
      }
      function settleDemoGeometry(ordinal) {
        var slide = deck.slides[ordinal - 1];
        var page = slide && slide.runtime ? state.pages.get(slide.id) : null;
        if (!slide || !slide.runtime || !page || page.failed || page.viewMode !== "live") { return; }
        var points = VIEW.geometry(slide, page.evaluation);
        var target = [];
        for (var pointIndex = 0; pointIndex < points.length; pointIndex += 1) {
          target.push({ x: points[pointIndex].x, y: points[pointIndex].y });
        }
        paintGeometry(slide, points, target);
      }
      function cancelDemo(reason, returnFocus, restoreFollows) {
        if (!demoActive) { return false; }
        demoGeneration += 1;
        demoActive = false;
        demoControl.setAttribute("aria-pressed", "false");
        clearDemoTimers();
        demoTouchedOrdinals.forEach(function (ordinal) {
          cancelOrdinal(ordinal);
          settleDemoGeometry(ordinal);
        });
        demoTouchedOrdinals.clear();
        hideDemoCue();
        if (!restoreFollows) {
          while (state.overlays.length) { closeOverlay(); }
        }
        demoStatus(reason);
        if (returnFocus !== false && document.contains(demoControl)) { demoControl.focus(); }
        demoEvent("deck:demo-end", demoEndDetail("cancelled"));
        return true;
      }
      function slideIndexById(slideId) {
        for (var index = 0; index < deck.slides.length; index += 1) {
          if (deck.slides[index].id === slideId) { return index; }
        }
        invariant(false, "E_DEMO_GOTO");
      }
      function ensureDemoTarget(slide, action) {
        if (action.type === "closeEvidence" && (!state.overlays.length || state.overlays[state.overlays.length - 1].kind !== "evidence")) {
          overlayOpeners.push(demoControl);
          dispatch({ type: "OPEN_EVIDENCE", tab: slide.runtime.scene.evidence.sources.length ? "sources" : "assumptions" }, { announce: false, url: false });
        }
        if (action.type === "closePanel") {
          var panelPage = state.pages.get(slide.id);
          if (panelPage.inputs.get("panel") !== action.panel) {
            dispatch({ type: "SET_PANEL", panel: action.panel }, { announce: false, url: false });
          }
        }
      }
      function applyDemoAction(slide, action) {
        if (action.type === "set" || action.type === "select") {
          var demoControlDefinition = slide.runtime.controls.get(action.control);
          invariant(demoControlDefinition, "E_DEMO_ACTION");
          var raw = action.value;
          if (demoControlDefinition.kind === "range") {
            raw = DECIMAL.indexOf(DECIMAL.parse(action.value, slide.runtime.scene.scale), demoControlDefinition, slide.runtime.scene.scale);
          }
          dispatch({ type: "SET_CONTROL", id: action.control, raw: raw }, { announce: true });
        } else if (action.type === "openEvidence") {
          overlayOpeners.push(demoControl);
          dispatch({ type: "OPEN_EVIDENCE", tab: slide.runtime.scene.evidence.sources.length ? "sources" : "assumptions" }, { announce: slide.runtime.scene.type === "evidence_only", url: slide.runtime.scene.type === "evidence_only" });
        } else if (action.type === "closeEvidence") {
          closeOverlay();
        } else if (action.type === "openPanel") {
          dispatch({ type: "SET_PANEL", panel: action.panel }, { announce: true });
        } else if (action.type === "closePanel") {
          dispatch({ type: "SET_PANEL", panel: null }, { announce: true });
        } else if (action.type === "goto") {
          navigate(slideIndexById(action.slideId), false);
        } else {
          invariant(action.type === "wait", "E_DEMO_ACTION");
        }
      }
      function startDemo(startEvent) {
        if (startEvent && suppressedDemoEvent === startEvent) {
          suppressedDemoEvent = null;
          return;
        }
        if (suppressDemoClick) {
          suppressDemoClick = false;
          return;
        }
        if (demoActive) { cancelDemo("cancelled", true); return; }
        clearOverlays();
        closeTooltip(false);
        demoGeneration += 1;
        var token = demoGeneration;
        demoActive = true;
        demoTouchedOrdinals.clear();
        demoControl.setAttribute("aria-pressed", "true");
        presenterStatus.textContent = deck.payload.lang === "ja" ? "デモを開始しました" : "Demo started";
        hideDemoCue();
        var sequence = [];
        for (var slideIndex = 0; slideIndex < deck.slides.length; slideIndex += 1) {
          var sequenceSlide = deck.slides[slideIndex];
          sequence.push({ kind: "page", slide: sequenceSlide, index: slideIndex });
          if (sequenceSlide.runtime) {
            for (var stepIndex = 0; stepIndex < sequenceSlide.runtime.scene.steps.length; stepIndex += 1) {
              sequence.push({ kind: "step", slide: sequenceSlide, step: sequenceSlide.runtime.scene.steps[stepIndex] });
            }
          }
          sequence.push({ kind: "pause", delay: 800 });
        }
        var cursor = 0;
        function advance() {
          if (!demoActive || token !== demoGeneration) { return; }
          if (cursor >= sequence.length) {
            demoActive = false;
            demoControl.setAttribute("aria-pressed", "false");
            clearDemoTimers();
            demoTouchedOrdinals.forEach(function (ordinal) {
              cancelOrdinal(ordinal);
              settleDemoGeometry(ordinal);
            });
            demoTouchedOrdinals.clear();
            hideDemoCue();
            openPresenterOverlay("overview", demoControl);
            demoStatus("complete");
            demoEvent("deck:demo-end", demoEndDetail("complete"));
            return;
          }
          var item = sequence[cursor];
          cursor += 1;
          demoAdvanceOrdinal = item.slide ? item.slide.ordinal : state.currentIndex + 1;
          if (item.kind === "page") {
            hideDemoCue();
            navigate(item.index, false);
            if (item.slide.runtime) {
              demoTouchedOrdinals.add(item.slide.ordinal);
              dispatch({ type: "RESET_PAGE" }, { announce: false });
            }
            scheduleDemo(advance, 0, token);
            return;
          }
          if (item.kind === "pause") {
            hideDemoCue();
            scheduleDemo(advance, state.reducedMotion ? Math.min(80, item.delay) : item.delay, token);
            return;
          }
          var step = item.step;
          var action = step.action;
          demoTouchedOrdinals.add(item.slide.ordinal);
          if (step.targetKey) {
            ensureDemoTarget(item.slide, action);
            positionDemoCue(item.slide, step.targetKey);
          } else {
            hideDemoCue();
          }
          var detail = { slideId: item.slide.id, stepKey: step.stepKey, ordinal: item.slide.ordinal, reason: "step" };
          if (step.targetKey) { detail.targetKey = step.targetKey; }
          applyDemoAction(item.slide, action);
          if (step.targetKey) { positionDemoCue(item.slide, step.targetKey, true); }
          demoEvent("deck:demo-step", detail);
          var delay = action.type === "wait" ? action.ms : 800;
          scheduleDemo(advance, state.reducedMotion ? Math.min(80, delay) : delay, token);
        }
        scheduleDemo(advance, 0, token);
      }
      function focusNeedsRepair() {
        var active = document.activeElement;
        if (!active || !document.contains(active) || active.nodeType !== 1) {
          return true;
        }
        if (active.hidden || (typeof active.closest === "function" && active.closest("[hidden]"))) {
          return true;
        }
        var activeDialog = typeof active.closest === "function" ? active.closest(".evidence-dialog,.presenter-dialog") : null;
        if (activeDialog && !activeDialog.hidden) {
          return false;
        }
        return Boolean(active.inert || (typeof active.closest === "function" && active.closest("[inert]")) || (activeDialog && activeDialog.hidden));
      }
      function restore(hash, write) {
        var before = URL_STATE.serialize(state, deck);
        var previousIndex = state.currentIndex;
        var previous = state;
        var candidate = state;
        if (!write) { overlayOpeners = []; }
        var parsed = URL_STATE.parse(hash, deck);
        candidate = STATE.reduce(candidate, { type: "CLEAR_OVERLAYS" }, deck);
        if (parsed.index !== candidate.currentIndex) {
          closeTooltip(false);
          candidate = STATE.reduce(candidate, { type: "NAVIGATE", index: parsed.index }, deck);
        }
        var slide = deck.slides[parsed.index];
        if (slide.runtime && parsed.values) {
          candidate = STATE.reduce(candidate, { type: "RESTORE_FRAGMENT", inputs: parsed.values, mode: parsed.mode }, deck);
        }
        state = candidate;
        try {
          render(null, { announce: false });
          if (!write && (parsed.index !== previousIndex || focusNeedsRepair())) {
            overlayOpeners = [];
            domById.get(slide.id).heading.focus();
          }
        } catch (failure) {
          state = previous;
          throw failure;
        }
        if (write) {
          writeUrl();
        }
        if (!write && parsed.valid && URL_STATE.serialize(state, deck) !== before) {
          emit("deck:state");
        }
      }

      function closeTooltip(focusTrigger) {
        if (!activeTooltip) { return; }
        var trigger = activeTooltip.trigger;
        activeTooltip.tooltip.hidden = true;
        trigger.setAttribute("aria-expanded", "false");
        activeTooltip = null;
        if (focusTrigger && document.contains(trigger)) { trigger.focus(); }
      }

      function openTooltip(trigger) {
        var tooltip = document.getElementById(trigger.getAttribute("aria-controls"));
        invariant(tooltip && tooltip.getAttribute("role") === "tooltip", "E_TOOLTIP_DOM");
        if (activeTooltip && activeTooltip.trigger !== trigger) { closeTooltip(false); }
        tooltip.hidden = false;
        trigger.setAttribute("aria-expanded", "true");
        activeTooltip = { trigger: trigger, tooltip: tooltip };
      }

      function bind() {
        for (var index = 0; index < deck.slides.length; index += 1) {
          (function (slide) {
            if (!slide.runtime) {
              return;
            }
            var dom = domById.get(slide.id);
            var controlList = slide.runtime.controlList || [];
            for (var controlIndex = 0; controlIndex < controlList.length; controlIndex += 1) {
              (function (control) {
                var controlDom = dom.controls.get(control.id);
                if (controlDom.range) {
                  controlDom.range.addEventListener("input", function () {
                    guard(slide.ordinal, "E_INPUT", function () {
                      if (state.currentIndex === slide.ordinal - 1) { dispatch({ type: "SET_CONTROL", id: control.id, raw: controlDom.range.value }, { announce: true }); }
                    });
                  });
                }
                if (controlDom.select) {
                  controlDom.select.addEventListener("change", function () {
                    guard(slide.ordinal, "E_INPUT", function () {
                      if (state.currentIndex === slide.ordinal - 1) { dispatch({ type: "SET_CONTROL", id: control.id, raw: controlDom.select.value }, { announce: true }); }
                    });
                  });
                }
                for (var buttonIndex = 0; buttonIndex < controlDom.buttons.length; buttonIndex += 1) {
                  (function (button) {
                    button.addEventListener("click", function (event) {
                      guard(slide.ordinal, "E_INPUT", function () {
                        if (state.currentIndex === slide.ordinal - 1) { dispatch({ type: "SET_CONTROL", id: control.id, raw: button.getAttribute("data-control-value") }, { announce: true, animate: event.detail !== 0 }); }
                      });
                    });
                  }(controlDom.buttons[buttonIndex]));
                }
              }(controlList[controlIndex]));
            }
            if (dom.panelSurface && slide.runtime.scene.type === "drilldown") {
              var panelOpeners = dom.panelSurface.querySelectorAll('[data-action="open-panel"]');
              for (var panelOpenerIndex = 0; panelOpenerIndex < panelOpeners.length; panelOpenerIndex += 1) {
                (function (panelOpener) {
                  panelOpener.addEventListener("click", function () {
                    guard(slide.ordinal, "E_PANEL_OPEN", function () {
                      panelReturnOpener = panelOpener;
                      dispatch({ type: "SET_PANEL", panel: panelOpener.getAttribute("data-panel-target") }, { announce: true });
                    });
                  });
                }(panelOpeners[panelOpenerIndex]));
              }
              var panelClosers = dom.panelSurface.querySelectorAll('[data-action="close-panel"]');
              for (var panelCloserIndex = 0; panelCloserIndex < panelClosers.length; panelCloserIndex += 1) {
                (function (panelCloser) {
                  panelCloser.addEventListener("click", function () {
                    guard(slide.ordinal, "E_PANEL_CLOSE", function () {
                      dispatch({ type: "SET_PANEL", panel: null }, { announce: true });
                      if (panelReturnOpener && document.contains(panelReturnOpener)) { panelReturnOpener.focus(); }
                      else { dom.heading.focus(); }
                      panelReturnOpener = null;
                    });
                  });
                }(panelClosers[panelCloserIndex]));
              }
            }
            if (dom.panelSurface && slide.runtime.scene.type === "accordion") {
              var accordionButtons = dom.panelSurface.querySelectorAll("[data-accordion-id]");
              for (var accordionIndex = 0; accordionIndex < accordionButtons.length; accordionIndex += 1) {
                (function (accordionButton) {
                  accordionButton.addEventListener("click", function () {
                    guard(slide.ordinal, "E_ACCORDION", function () {
                      var panelId = accordionButton.getAttribute("data-accordion-id");
                      var page = state.pages.get(slide.id);
                      var nextPanel = page.inputs.get("panel") === panelId && slide.runtime.scene.states.allowNone ? null : panelId;
                      dispatch({ type: "SET_PANEL", panel: nextPanel }, { announce: true });
                      accordionButton.focus();
                    });
                  });
                }(accordionButtons[accordionIndex]));
              }
              var accordionClosers = dom.panelSurface.querySelectorAll('[data-action="close-panel"]');
              for (var accordionCloserIndex = 0; accordionCloserIndex < accordionClosers.length; accordionCloserIndex += 1) {
                (function (accordionCloser) {
                  accordionCloser.addEventListener("click", function () {
                    guard(slide.ordinal, "E_ACCORDION_CLOSE", function () {
                      dispatch({ type: "SET_PANEL", panel: null }, { announce: true });
                      var matchingOpener = dom.panelSurface.querySelector('[data-accordion-id="' + accordionCloser.getAttribute("data-panel-target") + '"]');
                      if (matchingOpener) { matchingOpener.focus(); }
                    });
                  });
                }(accordionClosers[accordionCloserIndex]));
              }
            }
            var tooltipTriggers = dom.section.querySelectorAll("[data-tooltip-for]");
            for (var tooltipIndex = 0; tooltipIndex < tooltipTriggers.length; tooltipIndex += 1) {
              (function (tooltipTrigger) {
                tooltipTrigger.addEventListener("click", function (eventObject) {
                  guard(slide.ordinal, "E_TOOLTIP", function () {
                    eventObject.preventDefault();
                    if (activeTooltip && activeTooltip.trigger === tooltipTrigger) { closeTooltip(true); }
                    else { openTooltip(tooltipTrigger); }
                  });
                });
                tooltipTrigger.addEventListener("keydown", function (eventObject) {
                  guard(slide.ordinal, "E_TOOLTIP_KEY", function () {
                    if (eventObject.key === "Enter" || eventObject.key === " ") {
                      eventObject.preventDefault();
                      eventObject.stopPropagation();
                      openTooltip(tooltipTrigger);
                    } else if (eventObject.key === "Escape" && activeTooltip && activeTooltip.trigger === tooltipTrigger) {
                      eventObject.preventDefault();
                      eventObject.stopPropagation();
                      closeTooltip(true);
                    }
                  });
                });
              }(tooltipTriggers[tooltipIndex]));
            }
            dom.reset.addEventListener("click", function () { guard(slide.ordinal, "E_RESET", function () { dispatch({ type: "RESET_PAGE" }, { announce: true }); }); });
            dom.toggle.addEventListener("click", function () {
              guard(slide.ordinal, "E_STATIC_TOGGLE", function () {
                var page = state.pages.get(slide.id);
                dispatch({ type: "SET_MODE", mode: page.viewMode === "live" ? "static" : "live" }, { announce: false });
                dom.toggle.focus();
              });
            });
            dom.evidence.addEventListener("click", function () {
              guard(slide.ordinal, "E_OVERLAY_OPEN", function () {
                overlayOpeners.push(dom.evidence);
                var declaredEvidenceState = slide.runtime.scene.type === "evidence_only";
                dispatch({ type: "OPEN_EVIDENCE", tab: slide.runtime.scene.evidence.sources.length ? "sources" : "assumptions" }, { announce: declaredEvidenceState, url: declaredEvidenceState });
              });
            });
            dom.dialog.querySelector('[data-action="evidence-close"]').addEventListener("click", function () { guard(slide.ordinal, "E_OVERLAY_CLOSE", closeOverlay); });
            var tabs = dom.dialog.querySelectorAll("[data-evidence-tab]");
            for (var tabIndex = 0; tabIndex < tabs.length; tabIndex += 1) {
              (function (tab) {
                tab.addEventListener("click", function () {
                  guard(slide.ordinal, "E_OVERLAY_TAB", function () {
                    var declaredEvidenceState = slide.runtime.scene.type === "evidence_only";
                    dispatch({ type: "SET_EVIDENCE_TAB", tab: tab.getAttribute("data-evidence-tab") }, { announce: declaredEvidenceState, url: declaredEvidenceState });
                    tab.focus();
                  });
                });
                tab.addEventListener("keydown", function (eventObject) {
                  guard(slide.ordinal, "E_OVERLAY_KEY", function () {
                    if (["ArrowLeft", "ArrowRight", "Home", "End"].indexOf(eventObject.key) < 0) {
                      return;
                    }
                    eventObject.preventDefault();
                    var current = 0;
                    for (var index = 0; index < tabs.length; index += 1) {
                      if (tabs[index] === tab) {
                        current = index;
                      }
                    }
                    var next = eventObject.key === "Home" ? 0 : eventObject.key === "End" ? tabs.length - 1 : eventObject.key === "ArrowRight" ? (current + 1) % tabs.length : (current + tabs.length - 1) % tabs.length;
                    var declaredEvidenceState = slide.runtime.scene.type === "evidence_only";
                    dispatch({ type: "SET_EVIDENCE_TAB", tab: tabs[next].getAttribute("data-evidence-tab") }, { announce: declaredEvidenceState, url: declaredEvidenceState });
                    tabs[next].focus();
                  });
                });
              }(tabs[tabIndex]));
            }
          }(deck.slides[index]));
        }
        var presenterActions = ["overview", "replay", "demo", "fullscreen", "help"];
        for (var presenterActionIndex = 0; presenterActionIndex < presenterActions.length; presenterActionIndex += 1) {
          (function (actionName) {
            var actionButton = document.querySelector('[data-presenter-action="' + actionName + '"]');
            invariant(actionButton, "E_PRESENTER_DOM");
            actionButton.addEventListener("click", function (eventObject) {
              guard(0, "E_PRESENTER_ACTION", function () {
                if (actionName === "overview" || actionName === "help") { openPresenterOverlay(actionName, actionButton); }
                else if (actionName === "replay") { replayCurrent(); }
                else if (actionName === "demo") { startDemo(eventObject); }
                else { toggleFullscreen(); }
              });
            });
          }(presenterActions[presenterActionIndex]));
        }
        var presenterClosers = document.querySelectorAll("[data-presenter-close]");
        invariant(presenterClosers.length === 2, "E_PRESENTER_DOM");
        for (var presenterCloserIndex = 0; presenterCloserIndex < presenterClosers.length; presenterCloserIndex += 1) {
          presenterClosers[presenterCloserIndex].addEventListener("click", function () {
            guard(0, "E_PRESENTER_CLOSE", closeOverlay);
          });
        }
        var overviewButtons = document.querySelectorAll("[data-overview-slide]");
        invariant(overviewButtons.length === deck.slides.length, "E_PRESENTER_DOM");
        for (var overviewIndex = 0; overviewIndex < overviewButtons.length; overviewIndex += 1) {
          (function (button, pageIndex) {
            invariant(button.getAttribute("data-overview-slide") === String(pageIndex + 1), "E_PRESENTER_DOM");
            button.addEventListener("click", function () {
              guard(0, "E_OVERVIEW_NAV", function () { navigate(pageIndex, true); });
            });
          }(overviewButtons[overviewIndex], overviewIndex));
        }
        document.addEventListener("fullscreenchange", function () {
          guard(0, "E_FULLSCREEN_CHANGE", function () {
            var fullscreenButton = document.querySelector('[data-presenter-action="fullscreen"]');
            if (document.fullscreenElement) { setLocalFullscreen(false); }
            if (fullscreenButton) { fullscreenButton.setAttribute("aria-pressed", document.fullscreenElement || document.documentElement.classList.contains("idrt-local-fullscreen") ? "true" : "false"); }
          });
        });
        document.addEventListener("keydown", function (eventObject) {
          if (demoActive) {
            suppressedDemoEvent = eventObject;
            cancelDemo("cancelled", true);
            eventObject.preventDefault();
            eventObject.stopImmediatePropagation();
          }
        }, true);
        document.addEventListener("pointerdown", function (eventObject) {
          if (demoActive) {
            suppressDemoClick = eventObject.target === demoControl || demoControl.contains(eventObject.target);
            cancelDemo("cancelled", true);
            eventObject.preventDefault();
          }
        }, { capture: true });
        document.addEventListener("touchstart", function () {
          if (demoActive) { cancelDemo("cancelled", true); }
        }, { capture: true, passive: true });
        document.addEventListener("wheel", function () {
          if (demoActive) { cancelDemo("cancelled", true); }
        }, { capture: true, passive: true });
        document.addEventListener("pointerdown", function (eventObject) {
          guard(0, "E_TOOLTIP_POINTER", function () {
            if (activeTooltip && eventObject.target !== activeTooltip.trigger && !activeTooltip.tooltip.contains(eventObject.target)) { closeTooltip(false); }
          });
        }, true);
        media.addEventListener("change", function (eventObject) { guard(0, "E_MEDIA", function () { dispatch({ type: "SET_REDUCED_MOTION", value: eventObject.matches }, { announce: false, url: false }); }); });
        window.addEventListener("resize", function () { guard(0, "E_VIEWPORT", fitLiveViewports); });
        window.addEventListener("hashchange", function () {
          guard(0, "E_HASH", function () {
            var currentHash = window.location.hash;
            if (pendingHash === currentHash) {
              pendingHash = null;
              return;
            }
            pendingHash = null;
            var cancelledDemo = cancelDemo("cancelled", false, true);
            restore(currentHash, false);
            if (cancelledDemo && document.contains(demoControl)) { demoControl.focus(); }
          });
        });
      }

      try {
        updateNavigation = NAVIGATION.install({
          guard: guard,
          navigate: navigate,
          reset: replayCurrent,
          overlayOpen: function () { return state.overlays.length > 0; },
          closeOverlay: closeOverlay,
          openPresenter: openPresenterOverlay,
          startDemo: startDemo,
          toggleFullscreen: toggleFullscreen,
          currentIndex: function () { return state.currentIndex; }
        }, deck, scheduler);
        bind();
        restore(window.location.hash, true);
      } catch (failure) {
        dispose();
        throw failure;
      }
      return Object.freeze({
        dispose: dispose,
        failScene: failScene,
        failAllScenes: failAllScenes,
        snapshot: snapshot,
        ready: function () {
          document.documentElement.setAttribute("data-interactive-runtime", "ready");
          emit("deck:ready");
          if (startDemoOnReady) {
            startDemoOnReady = false;
            startDemo(null);
          }
        }
      });
    }
    return Object.freeze({ create: create });
  }());

  function resolveScheduler() {
    var injectionKey = "__IDRT_TEST_SCHEDULER__";
    var injectionDescriptor = Object.getOwnPropertyDescriptor(window, injectionKey);
    if (!injectionDescriptor) {
      invariant(!(injectionKey in window), "E_TEST_SCHEDULER");
    } else {
      invariant(injectionDescriptor.configurable === true && Object.prototype.hasOwnProperty.call(injectionDescriptor, "value"), "E_TEST_SCHEDULER");
      var injected = injectionDescriptor.value;
      var consumed = false;
      try { consumed = delete window.__IDRT_TEST_SCHEDULER__; } catch (ignoredSchedulerDelete) {}
      invariant(consumed && !Object.prototype.hasOwnProperty.call(window, injectionKey) && !(injectionKey in window), "E_TEST_SCHEDULER");
      invariant(plain(injected), "E_TEST_SCHEDULER");
      var methods = ["now", "setTimeout", "clearTimeout", "requestAnimationFrame", "cancelAnimationFrame"];
      var prototype = Object.getPrototypeOf(injected);
      invariant(prototype === Object.prototype || prototype === null, "E_TEST_SCHEDULER");
      var keys = Reflect.ownKeys(injected);
      invariant(keys.length === methods.length, "E_TEST_SCHEDULER");
      for (var keyIndex = 0; keyIndex < keys.length; keyIndex += 1) {
        invariant(typeof keys[keyIndex] === "string" && methods.indexOf(keys[keyIndex]) !== -1, "E_TEST_SCHEDULER");
      }
      for (var index = 0; index < methods.length; index += 1) {
        var methodDescriptor = Object.getOwnPropertyDescriptor(injected, methods[index]);
        invariant(methodDescriptor && Object.prototype.hasOwnProperty.call(methodDescriptor, "value") && typeof methodDescriptor.value === "function", "E_TEST_SCHEDULER");
      }
      return {
        now: function () { return injected.now(); },
        setTimeout: function (callback, delay) { return injected.setTimeout(callback, delay); },
        clearTimeout: function (handle) { injected.clearTimeout(handle); },
        requestAnimationFrame: function (callback) { return injected.requestAnimationFrame(callback); },
        cancelAnimationFrame: function (handle) { injected.cancelAnimationFrame(handle); }
      };
    }
    return {
      now: function () { return performance.now(); },
      setTimeout: function (callback, delay) { return window.setTimeout(callback, delay); },
      clearTimeout: function (handle) { window.clearTimeout(handle); },
      requestAnimationFrame: function (callback) { return window.requestAnimationFrame(callback); },
      cancelAnimationFrame: function (handle) { window.cancelAnimationFrame(handle); }
    };
  }

  var scheduler = Object.freeze(resolveScheduler());

  function restoreStaticDocument() {
    try { document.documentElement.setAttribute("data-interactive-runtime", "static"); } catch (ignoredRoot) {}
    var sections = document.querySelectorAll("#idrt-deck-pages > .slide");
    for (var index = 0; index < sections.length; index += 1) {
      var section = sections[index];
      try { section.hidden = false; } catch (ignoredSectionVisibility) {}
      try { section.inert = false; } catch (ignoredSectionInert) {}
      if (!section.hasAttribute("data-runtime")) {
        continue;
      }
      try { section.setAttribute("data-runtime", "static"); } catch (ignoredRuntime) {}
      try { section.removeAttribute("data-error-code"); } catch (ignoredErrorCode) {}
      var fallback = section.querySelector(".fallback-layer");
      var live = section.querySelector(".live-layer");
      var summary = section.querySelector(".scene-summary");
      var liveSummary = section.querySelector(".live-summary");
      var rail = section.querySelector(".control-rail");
      var dialog = section.querySelector(".evidence-dialog");
      try { if (fallback) { fallback.hidden = false; } } catch (ignoredFallback) {}
      try { if (live) { live.hidden = true; } } catch (ignoredLive) {}
      try { if (summary) { summary.hidden = false; summary.removeAttribute("aria-hidden"); } } catch (ignoredSummary) {}
      try { if (liveSummary) { liveSummary.hidden = true; liveSummary.setAttribute("aria-hidden", "true"); } } catch (ignoredLiveSummary) {}
      try { if (rail) { rail.hidden = true; } } catch (ignoredRail) {}
      try { if (dialog) { dialog.hidden = true; } } catch (ignoredDialog) {}
      var controls = section.querySelectorAll("input,button");
      for (var controlIndex = 0; controlIndex < controls.length; controlIndex += 1) {
        try { controls[controlIndex].disabled = true; } catch (ignoredControl) {}
      }
      var evidence = section.querySelector('[data-action="evidence"]');
      try { if (evidence) { evidence.setAttribute("aria-expanded", "false"); } } catch (ignoredEvidence) {}
    }
    try { document.getElementById("idrt-deck-pages").inert = false; } catch (ignoredMain) {}
    try { document.getElementById("idrt-presenter-chrome").inert = false; } catch (ignoredChrome) {}
  }

  var controller = null;
  var apiInstalled = false;
  function handleWindowError(event) {
    event.preventDefault();
    if (controller) {
      controller.failAllScenes("E_UNHANDLED_ERROR");
    }
  }
  function handleUnhandledRejection(event) {
    event.preventDefault();
    if (controller) {
      controller.failAllScenes("E_UNHANDLED_REJECTION");
    }
  }
  try {
    var deck = DATA.load();
    if (Object.getOwnPropertyDescriptor(window, "InteractiveDeck")) {
      throw new Error("E_API_OCCUPIED");
    }
    controller = CONTROLLER.create(deck, scheduler);
    window.addEventListener("error", handleWindowError);
    window.addEventListener("unhandledrejection", handleUnhandledRejection);
    var publicApi = Object.freeze({ snapshot: controller.snapshot });
    Object.defineProperty(window, "InteractiveDeck", { value: publicApi, writable: false, configurable: true, enumerable: true });
    apiInstalled = true;
    controller.ready();
    Object.defineProperty(window, "InteractiveDeck", { value: publicApi, writable: false, configurable: false, enumerable: true });
  } catch (failure) {
    try { window.removeEventListener("error", handleWindowError); } catch (ignoredErrorHandler) {}
    try { window.removeEventListener("unhandledrejection", handleUnhandledRejection); } catch (ignoredRejectionHandler) {}
    if (apiInstalled) {
      try { delete window.InteractiveDeck; } catch (ignoredApiRollback) {}
      apiInstalled = false;
    }
    if (controller) {
      try { controller.dispose(); } catch (ignoredDispose) {}
    }
    controller = null;
    restoreStaticDocument();
    console.error("[interactive-deck] page-1 E_BOOT: Interactive deck remained static.");
  }
}());
