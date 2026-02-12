/**
 * Camarad.ai — Procedural SVG Avatar System
 * Level 1: Dynamic 2D avatars with expressions & idle animations
 * 
 * Each agent gets a unique, role-appropriate character with:
 * - Distinct face shape, hairstyle, accessories per role
 * - 5 expressions: neutral, smile, think, surprised, serious
 * - Idle animations: blink, breathe, subtle head tilt
 * - Color customization (skin, hair, accent)
 * 
 * Zero external images — pure procedural SVG
 */

window.CamaradAvatars = (function() {
  'use strict';

  // ═══════════════════════════════════════════════════════════════
  // ── AGENT PROFILES (appearance + personality per role) ────────
  // ═══════════════════════════════════════════════════════════════
  var PROFILES = {
    // ── Business Suite ──
    'ceo-strategy': {
      gender: 'M', skinTone: '#D4A574', hairColor: '#2C2C2C', accentColor: '#1f6feb',
      hair: 'short-parted', accessory: 'tie', attire: 'suit-dark',
      faceShape: 'square', label: 'CEO'
    },
    'cto-innovation': {
      gender: 'M', skinTone: '#C68642', hairColor: '#1A1A1A', accentColor: '#8957e5',
      hair: 'short-messy', accessory: 'glasses-round', attire: 'hoodie',
      faceShape: 'oval', label: 'CTO'
    },
    'cmo-growth': {
      gender: 'F', skinTone: '#FDBCB4', hairColor: '#8B4513', accentColor: '#e5534b',
      hair: 'long-wavy', accessory: 'earrings', attire: 'blazer',
      faceShape: 'oval', label: 'CMO'
    },
    'cfo-finance': {
      gender: 'M', skinTone: '#E0AC69', hairColor: '#4A4A4A', accentColor: '#3fb950',
      hair: 'short-neat', accessory: 'glasses-square', attire: 'suit-grey',
      faceShape: 'round', label: 'CFO'
    },
    'coo-operations': {
      gender: 'F', skinTone: '#D4A574', hairColor: '#2C1810', accentColor: '#d29922',
      hair: 'bun', accessory: 'headset', attire: 'blouse',
      faceShape: 'oval', label: 'COO'
    },
    // ── Agency Suite ──
    'ppc-specialist': {
      gender: 'M', skinTone: '#FDBCB4', hairColor: '#5C4033', accentColor: '#58a6ff',
      hair: 'short-fade', accessory: 'headphones', attire: 'tshirt',
      faceShape: 'square', label: 'PPC'
    },
    'seo-content': {
      gender: 'F', skinTone: '#E0AC69', hairColor: '#1A1A1A', accentColor: '#3fb950',
      hair: 'bob', accessory: 'glasses-cat', attire: 'sweater',
      faceShape: 'heart', label: 'SEO'
    },
    'creative-director': {
      gender: 'F', skinTone: '#C68642', hairColor: '#FF6B6B', accentColor: '#f778ba',
      hair: 'pixie', accessory: 'beret', attire: 'artsy',
      faceShape: 'oval', label: 'Design'
    },
    'social-media': {
      gender: 'F', skinTone: '#FDBCB4', hairColor: '#6B4226', accentColor: '#d29922',
      hair: 'ponytail', accessory: 'phone', attire: 'casual',
      faceShape: 'round', label: 'Social'
    },
    'performance-analytics': {
      gender: 'M', skinTone: '#D4A574', hairColor: '#2C2C2C', accentColor: '#1f6feb',
      hair: 'short-neat', accessory: 'glasses-square', attire: 'shirt',
      faceShape: 'oval', label: 'Analytics'
    },
    // ── Development Suite ──
    'devops-infra': {
      gender: 'M', skinTone: '#E0AC69', hairColor: '#1A1A1A', accentColor: '#f0883e',
      hair: 'beanie', accessory: 'beard', attire: 'hoodie',
      faceShape: 'square', label: 'DevOps'
    },
    'fullstack-dev': {
      gender: 'M', skinTone: '#FDBCB4', hairColor: '#3A2410', accentColor: '#8957e5',
      hair: 'short-messy', accessory: 'headphones', attire: 'tshirt',
      faceShape: 'oval', label: 'FullStack'
    },
    'backend-architect': {
      gender: 'M', skinTone: '#C68642', hairColor: '#2C2C2C', accentColor: '#58a6ff',
      hair: 'short-parted', accessory: 'glasses-round', attire: 'shirt',
      faceShape: 'square', label: 'Backend'
    },
    'frontend-uiux': {
      gender: 'F', skinTone: '#FDBCB4', hairColor: '#D4A017', accentColor: '#f778ba',
      hair: 'long-straight', accessory: 'stylus', attire: 'creative',
      faceShape: 'heart', label: 'UI/UX'
    },
    'security-quality': {
      gender: 'M', skinTone: '#D4A574', hairColor: '#4A4A4A', accentColor: '#da3633',
      hair: 'buzz', accessory: 'glasses-square', attire: 'tactical',
      faceShape: 'square', label: 'Security'
    },
    // ── Personal Suite ──
    'life-coach': {
      gender: 'F', skinTone: '#E0AC69', hairColor: '#8B4513', accentColor: '#3fb950',
      hair: 'long-wavy', accessory: 'none', attire: 'yoga',
      faceShape: 'oval', label: 'Coach'
    },
    'psychologist': {
      gender: 'F', skinTone: '#D4A574', hairColor: '#2C1810', accentColor: '#6e40c9',
      hair: 'bob', accessory: 'glasses-round', attire: 'cardigan',
      faceShape: 'oval', label: 'Psych'
    },
    'personal-mentor': {
      gender: 'M', skinTone: '#C68642', hairColor: '#4A4A4A', accentColor: '#d29922',
      hair: 'short-parted', accessory: 'bowtie', attire: 'professor',
      faceShape: 'round', label: 'Mentor'
    },
    'fitness-wellness': {
      gender: 'M', skinTone: '#FDBCB4', hairColor: '#3A2410', accentColor: '#f0883e',
      hair: 'short-fade', accessory: 'sweatband', attire: 'athletic',
      faceShape: 'square', label: 'Fitness'
    },
    'creative-muse': {
      gender: 'F', skinTone: '#E0AC69', hairColor: '#7B2D8E', accentColor: '#f778ba',
      hair: 'long-curly', accessory: 'star', attire: 'bohemian',
      faceShape: 'heart', label: 'Muse'
    },
    // ── Extended slugs (alternative naming on some pages) ──
    'marketing-specialist': {
      gender: 'F', skinTone: '#FDBCB4', hairColor: '#8B4513', accentColor: '#e5534b',
      hair: 'long-wavy', accessory: 'earrings', attire: 'blazer',
      faceShape: 'oval', label: 'Marketing'
    },
    'sales-expert': {
      gender: 'M', skinTone: '#D4A574', hairColor: '#2C2C2C', accentColor: '#d29922',
      hair: 'short-parted', accessory: 'tie', attire: 'suit-dark',
      faceShape: 'square', label: 'Sales'
    },
    'social-media-manager': {
      gender: 'F', skinTone: '#FDBCB4', hairColor: '#6B4226', accentColor: '#d29922',
      hair: 'ponytail', accessory: 'phone', attire: 'casual',
      faceShape: 'round', label: 'Social'
    }
  };

  // Darken / lighten helpers
  function darken(hex, pct) {
    var r = parseInt(hex.slice(1,3),16), g = parseInt(hex.slice(3,5),16), b = parseInt(hex.slice(5,7),16);
    r = Math.round(r * (1 - pct)); g = Math.round(g * (1 - pct)); b = Math.round(b * (1 - pct));
    return '#' + [r,g,b].map(function(c){return ('0'+Math.max(0,c).toString(16)).slice(-2);}).join('');
  }
  function lighten(hex, pct) {
    var r = parseInt(hex.slice(1,3),16), g = parseInt(hex.slice(3,5),16), b = parseInt(hex.slice(5,7),16);
    r = Math.round(r + (255-r)*pct); g = Math.round(g + (255-g)*pct); b = Math.round(b + (255-b)*pct);
    return '#' + [r,g,b].map(function(c){return ('0'+Math.min(255,c).toString(16)).slice(-2);}).join('');
  }
  function withAlpha(hex, alpha) {
    var r = parseInt(hex.slice(1,3),16), g = parseInt(hex.slice(3,5),16), b = parseInt(hex.slice(5,7),16);
    return 'rgba(' + r + ',' + g + ',' + b + ',' + alpha + ')';
  }

  function buildSilhouetteHairBack(style, color, dark) {
    switch(style) {
      case 'long-wavy':
      case 'long-straight':
      case 'long-curly':
        return '<path d="M22 39 Q22 17 50 12 Q78 17 78 39 L78 77 Q72 85 66 77 L66 50 Q66 36 50 32 Q34 36 34 50 L34 77 Q28 85 22 77 Z" fill="'+color+'"/>';
      case 'bob':
        return '<path d="M24 40 Q24 20 50 15 Q76 20 76 40 L76 60 Q71 67 66 60 L66 45 Q66 34 50 30 Q34 34 34 45 L34 60 Q29 67 24 60 Z" fill="'+color+'"/>';
      case 'ponytail':
        return '<path d="M27 38 Q27 22 50 16 Q73 22 73 38 L72 58 Q68 64 64 58 L64 44 Q64 34 50 30 Q36 34 36 44 L36 58 Q32 64 28 58 Z" fill="'+color+'"/><ellipse cx="74" cy="44" rx="6" ry="11" fill="'+dark+'" opacity="0.7"/>';
      default:
        return '';
    }
  }

  function buildSilhouetteHairFront(style, color, dark, light) {
    switch(style) {
      case 'short-parted':
        return '<path class="avatar-hair-front" d="M26 37 Q26 18 50 14 Q74 18 74 37 L71 33 Q68 22 50 20 Q32 22 29 33 Z" fill="'+color+'"/><path d="M42 16 Q50 13 58 16 L54 19 Q50 17 46 19 Z" fill="'+light+'" opacity="0.3"/>';
      case 'short-messy':
        return '<path class="avatar-hair-front" d="M26 37 Q24 16 50 11 Q76 16 74 37 L71 30 Q67 19 50 16 Q33 19 29 30 Z" fill="'+color+'"/><path d="M34 14 L38 18 L33 17 Z" fill="'+dark+'"/><path d="M60 13 L65 17 L58 17 Z" fill="'+dark+'"/>';
      case 'short-fade':
      case 'short-neat':
      case 'buzz':
        return '<path class="avatar-hair-front" d="M27 39 Q27 22 50 17 Q73 22 73 39 L71 34 Q68 24 50 21 Q32 24 29 34 Z" fill="'+color+'" opacity="'+(style === 'buzz' ? '0.7' : '1')+'"/>';
      case 'long-wavy':
      case 'long-straight':
      case 'long-curly':
        return '<path class="avatar-hair-front" d="M23 37 Q23 14 50 10 Q77 14 77 37 L74 31 Q71 18 50 15 Q29 18 26 31 Z" fill="'+color+'"/>';
      case 'bob':
        return '<path class="avatar-hair-front" d="M24 37 Q24 16 50 12 Q76 16 76 37 L73 32 Q70 20 50 17 Q30 20 27 32 Z" fill="'+color+'"/><path d="M31 31 Q36 26 41 29 Q46 24 50 27 Q54 24 59 29 Q64 26 69 31" fill="'+color+'" stroke="'+dark+'" stroke-width="0.4"/>';
      case 'pixie':
        return '<path class="avatar-hair-front" d="M27 38 Q27 19 50 14 Q73 19 73 36 L70 31 Q66 22 50 19 Q34 22 30 31 Z" fill="'+color+'"/>';
      case 'ponytail':
        return '<path class="avatar-hair-front" d="M27 37 Q27 18 50 14 Q73 18 73 37 L70 32 Q66 21 50 18 Q34 21 30 32 Z" fill="'+color+'"/>';
      case 'bun':
        return '<path class="avatar-hair-front" d="M27 37 Q27 18 50 14 Q73 18 73 37 L70 32 Q66 21 50 18 Q34 21 30 32 Z" fill="'+color+'"/><circle cx="50" cy="13" r="7" fill="'+dark+'" opacity="0.9"/>';
      case 'beanie':
        return '<path class="avatar-hair-front" d="M22 38 Q22 16 50 11 Q78 16 78 38 L76 33 Q72 20 50 16 Q28 20 24 33 Z" fill="#565b66"/><rect x="22" y="33" width="56" height="6" rx="2.5" fill="#6b7280"/>';
      default:
        return '<path class="avatar-hair-front" d="M27 38 Q27 20 50 16 Q73 20 73 38 L70 33 Q67 23 50 20 Q33 23 30 33 Z" fill="'+color+'"/>';
    }
  }

  function buildSilhouetteEyes(expr) {
    if (expr === 'surprised') return '<ellipse cx="39" cy="44" rx="4.4" ry="4.8" fill="#f8fbff"/><ellipse cx="61" cy="44" rx="4.4" ry="4.8" fill="#f8fbff"/><circle cx="39" cy="44.4" r="2.2" fill="#1b1f28"/><circle cx="61" cy="44.4" r="2.2" fill="#1b1f28"/>';
    if (expr === 'serious') return '<path d="M35 44 Q39 42 43 44" stroke="#f8fbff" stroke-width="1.8" fill="none" stroke-linecap="round"/><path d="M57 44 Q61 42 65 44" stroke="#f8fbff" stroke-width="1.8" fill="none" stroke-linecap="round"/>';
    if (expr === 'wink') return '<ellipse cx="39" cy="44" rx="4.1" ry="3.7" fill="#f8fbff"/><circle cx="39" cy="44.2" r="2.1" fill="#1b1f28"/><path d="M57 44 Q61 42 65 44" stroke="#f8fbff" stroke-width="1.8" fill="none" stroke-linecap="round"/>';
    if (expr === 'think') return '<ellipse cx="39" cy="44" rx="4.1" ry="3.7" fill="#f8fbff"/><ellipse cx="61" cy="44" rx="4.1" ry="3.7" fill="#f8fbff"/><circle cx="37.5" cy="43.2" r="2.1" fill="#1b1f28"/><circle cx="59.5" cy="43.2" r="2.1" fill="#1b1f28"/>';
    return '<ellipse cx="39" cy="44" rx="4.1" ry="3.7" fill="#f8fbff"/><ellipse cx="61" cy="44" rx="4.1" ry="3.7" fill="#f8fbff"/><circle cx="39" cy="44.2" r="2.1" fill="#1b1f28"/><circle cx="61" cy="44.2" r="2.1" fill="#1b1f28"/>';
  }

  function buildSilhouetteMouth(expr, lip) {
    if (expr === 'smile' || expr === 'excited') return '<path d="M42 59 Q50 65 58 59" stroke="'+lip+'" stroke-width="2.1" fill="none" stroke-linecap="round"/>';
    if (expr === 'surprised') return '<ellipse cx="50" cy="60" rx="3.2" ry="4.8" fill="'+darken(lip,0.25)+'"/>';
    if (expr === 'serious') return '<line x1="43" y1="60" x2="57" y2="60" stroke="'+darken(lip,0.22)+'" stroke-width="1.9" stroke-linecap="round"/>';
    if (expr === 'think') return '<path d="M44 60 Q50 62.5 56 60" stroke="'+lip+'" stroke-width="1.8" fill="none" stroke-linecap="round"/>';
    return '<path d="M44 59.5 Q50 62 56 59.5" stroke="'+lip+'" stroke-width="1.8" fill="none" stroke-linecap="round"/>';
  }

  function buildSilhouetteAccessory(type, accent) {
    if (type === 'glasses-round') return '<circle cx="39" cy="44" r="7" fill="none" stroke="#4b5563" stroke-width="1.4"/><circle cx="61" cy="44" r="7" fill="none" stroke="#4b5563" stroke-width="1.4"/><line x1="46" y1="44" x2="54" y2="44" stroke="#4b5563" stroke-width="1.2"/>';
    if (type === 'glasses-square') return '<rect x="32.5" y="38" width="13" height="11" rx="2" fill="none" stroke="#4b5563" stroke-width="1.4"/><rect x="54.5" y="38" width="13" height="11" rx="2" fill="none" stroke="#4b5563" stroke-width="1.4"/><line x1="45.5" y1="43.5" x2="54.5" y2="43.5" stroke="#4b5563" stroke-width="1.2"/>';
    if (type === 'headphones' || type === 'headset') return '<path d="M27 44 Q27 24 50 20 Q73 24 73 44" fill="none" stroke="#4b5563" stroke-width="2.2"/><rect x="23" y="40" width="5" height="10" rx="2" fill="#4b5563"/><rect x="72" y="40" width="5" height="10" rx="2" fill="#4b5563"/>';
    if (type === 'earrings') return '<circle cx="29" cy="56" r="1.5" fill="'+accent+'"/><circle cx="71" cy="56" r="1.5" fill="'+accent+'"/>';
    return '';
  }

  // ═══════════════════════════════════════════════════════════════
  // ── SVG BUILDER ──────────────────────────────────────────────
  // ═══════════════════════════════════════════════════════════════

  function buildSVG(slug, expression, size) {
    var p = PROFILES[slug];
    if (!p) p = { gender:'M', skinTone:'#D4A574', hairColor:'#2C2C2C', accentColor:'#58a6ff',
                  hair:'short-neat', accessory:'none', attire:'tshirt', faceShape:'oval', label:'AI' };

    expression = expression || 'neutral';
    size = size || 80;
    var uid = 'av-' + slug.replace(/[^a-z0-9]/g,'') + '-' + Math.random().toString(36).substr(2,4);

    var reduceMotion = false;
    try {
      reduceMotion = !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
    } catch (e) { reduceMotion = false; }

    var moodMap = {
      neutral:   { glow: 0.16, dot: '#60708a' },
      smile:     { glow: 0.28, dot: '#2fbf71' },
      think:     { glow: 0.24, dot: '#58a6ff' },
      surprised: { glow: 0.30, dot: '#f2b84b' },
      serious:   { glow: 0.18, dot: '#8b96a8' },
      wink:      { glow: 0.26, dot: '#c58bff' },
      excited:   { glow: 0.34, dot: '#f85149' }
    };
    var mood = moodMap[expression] || moodMap.neutral;

    var base = darken(p.accentColor, 0.62);
    var ring = lighten(p.accentColor, 0.2);
    var skin = p.skinTone;
    var skinDark = darken(skin, 0.12);
    var hair = p.hairColor || '#2C2C2C';
    var hairDark = darken(hair, 0.25);
    var hairLight = lighten(hair, 0.2);
    var attire = getAttireColor(p.attire, p.accentColor);
    var lip = p.gender === 'F' ? lighten('#b54f5c', 0.08) : '#a85b53';

    if (size <= 34) {
      var mini = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="'+size+'" height="'+size+'" class="camarad-avatar silhouette-avatar'+(reduceMotion ? ' reduce-motion' : '')+'" data-slug="'+slug+'" data-expr="'+expression+'">';
      mini += '<defs><radialGradient id="'+uid+'-mini" cx="30%" cy="20%"><stop offset="0%" stop-color="'+lighten(p.accentColor,0.38)+'"/><stop offset="100%" stop-color="'+base+'"/></radialGradient></defs>';
      mini += '<style>.silhouette-avatar .mini-core{animation:mini-breathe 3.2s ease-in-out infinite}.silhouette-avatar.reduce-motion .mini-core{animation:none}@keyframes mini-breathe{0%,100%{transform:translateY(0)}50%{transform:translateY(.7px)}}</style>';
      mini += '<circle cx="50" cy="50" r="48" fill="'+withAlpha(mood.dot, 0.16)+'"/>';
      mini += '<circle cx="50" cy="50" r="45" fill="url(#'+uid+'-mini)" stroke="'+ring+'" stroke-width="1.8"/>';
      mini += '<g class="mini-core" style="transform-origin:50px 55px"><ellipse cx="50" cy="67" rx="23" ry="14" fill="'+withAlpha(attire,0.95)+'"/><circle cx="50" cy="44" r="17" fill="'+skin+'"/><path d="M33 43 Q33 26 50 23 Q67 26 67 43 L64 39 Q61 30 50 29 Q39 30 36 39 Z" fill="'+hair+'"/></g>';
      mini += '<circle cx="80" cy="20" r="5" fill="'+mood.dot+'" stroke="#0d1117" stroke-width="1.2"/>';
      mini += '</svg>';
      return mini;
    }

    var svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="'+size+'" height="'+size+'" class="camarad-avatar silhouette-avatar'+(reduceMotion ? ' reduce-motion' : '')+'" data-slug="'+slug+'" data-expr="'+expression+'">';
    svg += '<defs>';
    svg += '<radialGradient id="'+uid+'-bg" cx="26%" cy="18%"><stop offset="0%" stop-color="'+lighten(p.accentColor,0.42)+'"/><stop offset="58%" stop-color="'+p.accentColor+'"/><stop offset="100%" stop-color="'+base+'"/></radialGradient>';
    svg += '<radialGradient id="'+uid+'-glow" cx="50%" cy="50%"><stop offset="0%" stop-color="'+mood.dot+'" stop-opacity="'+mood.glow+'"/><stop offset="100%" stop-color="'+mood.dot+'" stop-opacity="0"/></radialGradient>';
    svg += '<linearGradient id="'+uid+'-faceShade" x1="0%" y1="0%" x2="100%" y2="100%"><stop offset="0%" stop-color="'+lighten(skin,0.1)+'"/><stop offset="100%" stop-color="'+skinDark+'"/></linearGradient>';
    svg += '<linearGradient id="'+uid+'-coat" x1="0%" y1="0%" x2="0%" y2="100%"><stop offset="0%" stop-color="'+lighten(attire,0.06)+'"/><stop offset="100%" stop-color="'+darken(attire,0.15)+'"/></linearGradient>';
    svg += '<clipPath id="'+uid+'-portraitClip"><circle cx="50" cy="50" r="43.2"/></clipPath>';
    svg += '</defs>';
    svg += '<style>';
    svg += '.silhouette-avatar .avatar-body{transform-origin:50px 72px;animation:av-breathe 3.8s ease-in-out infinite;}';
    svg += '.silhouette-avatar .avatar-head{transform-origin:50px 47px;animation:av-head-turn 6.4s ease-in-out infinite;}';
    svg += '.silhouette-avatar .avatar-hair-front{transform-origin:50px 33px;animation:av-hair-sway 4.6s ease-in-out infinite;}';
    svg += '.silhouette-avatar .avatar-glow{animation:av-pulse 4.8s ease-in-out infinite;}';
    svg += '.silhouette-avatar .avatar-twitch{transform-origin:50px 47px;animation:av-twitch 11s ease-in-out infinite;}';
    svg += '.silhouette-avatar.reduce-motion .avatar-body,.silhouette-avatar.reduce-motion .avatar-head,.silhouette-avatar.reduce-motion .avatar-hair-front,.silhouette-avatar.reduce-motion .avatar-glow,.silhouette-avatar.reduce-motion .avatar-twitch{animation:none!important;}';
    svg += '@keyframes av-breathe{0%,100%{transform:translateY(0) scaleY(1);}50%{transform:translateY(.8px) scaleY(1.01);}}';
    svg += '@keyframes av-head-turn{0%,100%{transform:translateX(0) rotate(0deg);}30%{transform:translateX(-.8px) rotate(-1.2deg);}65%{transform:translateX(.9px) rotate(1.35deg);}}';
    svg += '@keyframes av-hair-sway{0%,100%{transform:rotate(0deg);}50%{transform:rotate(.9deg);}}';
    svg += '@keyframes av-pulse{0%,100%{opacity:.7;}50%{opacity:1;}}';
    svg += '@keyframes av-twitch{0%,76%,100%{transform:rotate(0deg);}78%{transform:rotate(.8deg);}80%{transform:rotate(-.5deg);}82%{transform:rotate(0deg);}}';
    svg += '</style>';

    svg += '<circle cx="50" cy="50" r="49" class="avatar-glow" fill="url(#'+uid+'-glow)"/>';
    svg += '<circle cx="50" cy="50" r="47" fill="url(#'+uid+'-bg)" stroke="'+ring+'" stroke-width="1.8"/>';
    svg += '<circle cx="50" cy="50" r="43.2" fill="none" stroke="'+withAlpha('#ffffff', 0.18)+'" stroke-width="0.8"/>';
    svg += '<ellipse cx="35" cy="29" rx="14" ry="7.5" fill="#ffffff" opacity="0.11"/>';

    svg += '<g clip-path="url(#'+uid+'-portraitClip)">';
    svg += '<g class="avatar-body">';
    svg += '<path d="M20 96 Q25 75 40 70 Q50 67 60 70 Q75 75 80 96 Z" fill="url(#'+uid+'-coat)"/>';
    svg += '<path d="M39 72 Q50 79 61 72 L59 70 Q50 74 41 70 Z" fill="'+withAlpha('#ffffff', 0.25)+'"/>';
    svg += '<ellipse cx="50" cy="67.5" rx="8.2" ry="6.8" fill="'+skinDark+'"/>';
    svg += '</g>';

    svg += '<g class="avatar-head avatar-twitch">';
    svg += buildSilhouetteHairBack(p.hair, hair, hairDark);
    svg += '<ellipse cx="50" cy="46" rx="24.6" ry="26.2" fill="url(#'+uid+'-faceShade)"/>';
    svg += '<ellipse cx="25.5" cy="49" rx="3.2" ry="5.2" fill="'+skinDark+'" opacity="0.9"/><ellipse cx="74.5" cy="49" rx="3.2" ry="5.2" fill="'+skinDark+'" opacity="0.9"/>';
    svg += buildSilhouetteHairFront(p.hair, hair, hairDark, hairLight);
    svg += '<path d="M34 37 Q39 35 44 37" stroke="'+darken(hair,0.38)+'" stroke-width="1.6" fill="none" stroke-linecap="round"/><path d="M56 37 Q61 35 66 37" stroke="'+darken(hair,0.38)+'" stroke-width="1.6" fill="none" stroke-linecap="round"/>';
    svg += buildSilhouetteEyes(expression);
    svg += '<path d="M49 49 Q50 53 51 49" stroke="'+darken(skin,0.3)+'" stroke-width="1.1" fill="none" opacity="0.62"/>';
    svg += buildSilhouetteMouth(expression, lip);
    if (p.gender === 'F') {
      svg += '<ellipse cx="33" cy="54" rx="4" ry="2.3" fill="'+withAlpha('#ff8ea0', 0.2)+'"/><ellipse cx="67" cy="54" rx="4" ry="2.3" fill="'+withAlpha('#ff8ea0', 0.2)+'"/>';
    }
    svg += buildSilhouetteAccessory(p.accessory, p.accentColor);
    svg += '</g>';

    svg += '<g class="avatar-blink" style="opacity:0">';
    svg += '<path d="M34 44 Q39 46 44 44" stroke="'+skinDark+'" stroke-width="2.2" fill="none" stroke-linecap="round"/>';
    svg += '<path d="M56 44 Q61 46 66 44" stroke="'+skinDark+'" stroke-width="2.2" fill="none" stroke-linecap="round"/>';
    svg += '</g>';
    svg += '</g>';

    svg += '<circle cx="81" cy="19" r="4.8" fill="'+mood.dot+'" stroke="#0d1117" stroke-width="1.3"/>';
    svg += '<circle cx="81" cy="19" r="2.2" fill="'+withAlpha('#ffffff', 0.35)+'"/>';
    svg += '</svg>';
    return svg;
  }

  // ── Head shapes ──
  function buildHead(shape, skin, skinDark) {
    switch(shape) {
      case 'square':
        return '<rect x="22" y="26" width="56" height="52" rx="18" fill="'+skin+'"/>';
      case 'round':
        return '<ellipse cx="50" cy="48" rx="28" ry="27" fill="'+skin+'"/>';
      case 'heart':
        return '<ellipse cx="50" cy="46" rx="27" ry="26" fill="'+skin+'"/>'
             + '<ellipse cx="50" cy="52" rx="22" ry="22" fill="'+skin+'"/>';
      default: // oval
        return '<ellipse cx="50" cy="47" rx="26" ry="28" fill="'+skin+'"/>';
    }
  }

  // ── Eyes (expression-dependent) ──
  function buildEyes(expr, gender) {
    var s = '';
    var eyeW = gender === 'F' ? 7 : 6;
    var eyeH = gender === 'F' ? 5 : 4.5;

    switch(expr) {
      case 'smile':
        // Happy eyes — slightly squinted
        s += '<ellipse cx="38" cy="43" rx="'+eyeW+'" ry="'+(eyeH-1)+'" fill="white"/>';
        s += '<ellipse cx="62" cy="43" rx="'+eyeW+'" ry="'+(eyeH-1)+'" fill="white"/>';
        s += '<circle cx="38" cy="43" r="2.5" fill="#1a1a1a"/>';
        s += '<circle cx="62" cy="43" r="2.5" fill="#1a1a1a"/>';
        s += '<circle cx="39" cy="42" r="0.8" fill="white"/>'; // sparkle
        s += '<circle cx="63" cy="42" r="0.8" fill="white"/>';
        break;
      case 'think':
        // Looking up-left
        s += '<ellipse cx="38" cy="42" rx="'+eyeW+'" ry="'+eyeH+'" fill="white"/>';
        s += '<ellipse cx="62" cy="42" rx="'+eyeW+'" ry="'+eyeH+'" fill="white"/>';
        s += '<circle cx="36" cy="41" r="2.8" fill="#1a1a1a"/>';
        s += '<circle cx="60" cy="41" r="2.8" fill="#1a1a1a"/>';
        break;
      case 'surprised':
        // Wide eyes
        s += '<ellipse cx="38" cy="42" rx="'+(eyeW+1)+'" ry="'+(eyeH+2)+'" fill="white"/>';
        s += '<ellipse cx="62" cy="42" rx="'+(eyeW+1)+'" ry="'+(eyeH+2)+'" fill="white"/>';
        s += '<circle cx="38" cy="42" r="3.5" fill="#1a1a1a"/>';
        s += '<circle cx="62" cy="42" r="3.5" fill="#1a1a1a"/>';
        s += '<circle cx="39.5" cy="40.5" r="1.2" fill="white"/>';
        s += '<circle cx="63.5" cy="40.5" r="1.2" fill="white"/>';
        break;
      case 'serious':
        // Narrowed
        s += '<ellipse cx="38" cy="43" rx="'+eyeW+'" ry="'+(eyeH-1.5)+'" fill="white"/>';
        s += '<ellipse cx="62" cy="43" rx="'+eyeW+'" ry="'+(eyeH-1.5)+'" fill="white"/>';
        s += '<circle cx="38" cy="43" r="2.5" fill="#1a1a1a"/>';
        s += '<circle cx="62" cy="43" r="2.5" fill="#1a1a1a"/>';
        break;
      case 'wink':
        // Left eye open, right eye winking (closed arc)
        s += '<ellipse cx="38" cy="42" rx="'+eyeW+'" ry="'+eyeH+'" fill="white"/>';
        s += '<circle cx="38" cy="42.5" r="3" fill="#1a1a1a"/>';
        s += '<circle cx="39" cy="41.5" r="1" fill="white"/>'; // sparkle
        s += '<path d="M56 43 Q62 40 68 43" stroke="#1a1a1a" stroke-width="2" fill="none" stroke-linecap="round"/>';
        break;
      case 'excited':
        // Wide sparkly eyes
        s += '<ellipse cx="38" cy="42" rx="'+(eyeW+0.5)+'" ry="'+(eyeH+1)+'" fill="white"/>';
        s += '<ellipse cx="62" cy="42" rx="'+(eyeW+0.5)+'" ry="'+(eyeH+1)+'" fill="white"/>';
        s += '<circle cx="38" cy="42" r="3" fill="#1a1a1a"/>';
        s += '<circle cx="62" cy="42" r="3" fill="#1a1a1a"/>';
        // Double sparkles
        s += '<circle cx="39.5" cy="40.5" r="1.2" fill="white"/>';
        s += '<circle cx="63.5" cy="40.5" r="1.2" fill="white"/>';
        s += '<circle cx="36" cy="41" r="0.6" fill="white"/>';
        s += '<circle cx="60" cy="41" r="0.6" fill="white"/>';
        break;
      default: // neutral
        s += '<ellipse cx="38" cy="42" rx="'+eyeW+'" ry="'+eyeH+'" fill="white"/>';
        s += '<ellipse cx="62" cy="42" rx="'+eyeW+'" ry="'+eyeH+'" fill="white"/>';
        s += '<circle cx="38" cy="42.5" r="3" fill="#1a1a1a"/>';
        s += '<circle cx="62" cy="42.5" r="3" fill="#1a1a1a"/>';
        s += '<circle cx="39" cy="41.5" r="1" fill="white"/>';
        s += '<circle cx="63" cy="41.5" r="1" fill="white"/>';
    }

    // Eyelashes for F
    if (gender === 'F') {
      s += '<line x1="31" y1="40" x2="33" y2="38" stroke="#1a1a1a" stroke-width="1" stroke-linecap="round"/>';
      s += '<line x1="55" y1="40" x2="57" y2="38" stroke="#1a1a1a" stroke-width="1" stroke-linecap="round"/>';
      s += '<line x1="43" y1="38" x2="45" y2="37" stroke="#1a1a1a" stroke-width="1" stroke-linecap="round"/>';
      s += '<line x1="67" y1="38" x2="69" y2="37" stroke="#1a1a1a" stroke-width="1" stroke-linecap="round"/>';
    }

    return s;
  }

  // ── Eyebrows ──
  function buildEyebrows(expr, gender) {
    var s = '';
    var thick = gender === 'M' ? 2 : 1.5;
    switch(expr) {
      case 'smile':
        s += '<path d="M32 36 Q38 33 44 35" stroke="#3a3a3a" stroke-width="'+thick+'" fill="none" stroke-linecap="round"/>';
        s += '<path d="M56 35 Q62 33 68 36" stroke="#3a3a3a" stroke-width="'+thick+'" fill="none" stroke-linecap="round"/>';
        break;
      case 'think':
        s += '<path d="M32 34 Q38 31 44 34" stroke="#3a3a3a" stroke-width="'+thick+'" fill="none" stroke-linecap="round"/>';
        s += '<path d="M56 35 Q62 33 68 37" stroke="#3a3a3a" stroke-width="'+thick+'" fill="none" stroke-linecap="round"/>';
        break;
      case 'surprised':
        s += '<path d="M32 33 Q38 29 44 33" stroke="#3a3a3a" stroke-width="'+thick+'" fill="none" stroke-linecap="round"/>';
        s += '<path d="M56 33 Q62 29 68 33" stroke="#3a3a3a" stroke-width="'+thick+'" fill="none" stroke-linecap="round"/>';
        break;
      case 'serious':
        s += '<path d="M32 36 Q38 34 44 37" stroke="#3a3a3a" stroke-width="'+(thick+0.5)+'" fill="none" stroke-linecap="round"/>';
        s += '<path d="M56 37 Q62 34 68 36" stroke="#3a3a3a" stroke-width="'+(thick+0.5)+'" fill="none" stroke-linecap="round"/>';
        break;
      case 'wink':
        s += '<path d="M32 34 Q38 31 44 34" stroke="#3a3a3a" stroke-width="'+thick+'" fill="none" stroke-linecap="round"/>';
        s += '<path d="M56 36 Q62 34 68 37" stroke="#3a3a3a" stroke-width="'+thick+'" fill="none" stroke-linecap="round"/>';
        break;
      case 'excited':
        s += '<path d="M32 33 Q38 30 44 33" stroke="#3a3a3a" stroke-width="'+thick+'" fill="none" stroke-linecap="round"/>';
        s += '<path d="M56 33 Q62 30 68 33" stroke="#3a3a3a" stroke-width="'+thick+'" fill="none" stroke-linecap="round"/>';
        break;
      default:
        s += '<path d="M32 35 Q38 32 44 35" stroke="#3a3a3a" stroke-width="'+thick+'" fill="none" stroke-linecap="round"/>';
        s += '<path d="M56 35 Q62 32 68 35" stroke="#3a3a3a" stroke-width="'+thick+'" fill="none" stroke-linecap="round"/>';
    }
    return s;
  }

  // ── Mouth ──
  function buildMouth(expr, gender) {
    var s = '';
    switch(expr) {
      case 'smile':
        s += '<path d="M40 58 Q50 66 60 58" stroke="#c44" stroke-width="2" fill="none" stroke-linecap="round"/>';
        if (gender === 'F') s += '<ellipse cx="50" cy="60" rx="6" ry="2" fill="#e88" opacity="0.4"/>';
        break;
      case 'think':
        s += '<ellipse cx="53" cy="59" rx="4" ry="2.5" fill="#c44" opacity="0.7"/>';
        break;
      case 'surprised':
        s += '<ellipse cx="50" cy="60" rx="5" ry="6" fill="#c44" opacity="0.8"/>';
        s += '<ellipse cx="50" cy="59" rx="3.5" ry="4" fill="#2a0a0a"/>';
        break;
      case 'serious':
        s += '<line x1="41" y1="59" x2="59" y2="59" stroke="#a55" stroke-width="2" stroke-linecap="round"/>';
        break;
      case 'wink':
        // Cheeky smirk
        s += '<path d="M40 57 Q50 64 58 56" stroke="#c44" stroke-width="1.8" fill="none" stroke-linecap="round"/>';
        break;
      case 'excited':
        // Big open smile with teeth
        s += '<path d="M38 57 Q50 68 62 57" stroke="#c44" stroke-width="2" fill="none" stroke-linecap="round"/>';
        s += '<path d="M42 58 Q50 63 58 58" fill="white" opacity="0.6"/>';
        if (gender === 'F') s += '<ellipse cx="50" cy="60" rx="7" ry="2.5" fill="#e88" opacity="0.35"/>';
        break;
      default:
        s += '<path d="M42 58 Q50 62 58 58" stroke="#b55" stroke-width="1.5" fill="none" stroke-linecap="round"/>';
        if (gender === 'F') {
          // subtle lipstick
          s += '<path d="M43 57 Q50 61 57 57" stroke="#d66" stroke-width="1" fill="none" opacity="0.4"/>';
        }
    }
    // Cheek blush for F
    if (gender === 'F' && (expr === 'smile' || expr === 'neutral')) {
      s += '<ellipse cx="28" cy="52" rx="5" ry="3" fill="#ff9999" opacity="0.2"/>';
      s += '<ellipse cx="72" cy="52" rx="5" ry="3" fill="#ff9999" opacity="0.2"/>';
    }
    return s;
  }

  // ── Nose ──
  function buildNose(gender) {
    if (gender === 'F') {
      return '<path d="M48 48 Q50 53 52 48" stroke="#b8967a" stroke-width="1" fill="none" opacity="0.5"/>';
    }
    return '<path d="M47 46 Q50 54 53 46" stroke="#a0856e" stroke-width="1.2" fill="none" opacity="0.6"/>';
  }

  // ── Hair back layer ──
  function buildHairBack(style, color, dark, gender) {
    var s = '';
    switch(style) {
      case 'long-wavy':
      case 'long-straight':
      case 'long-curly':
        s += '<path d="M18 40 Q18 20 50 15 Q82 20 82 40 L82 72 Q75 78 70 72 L70 45 Q70 30 50 25 Q30 30 30 45 L30 72 Q25 78 18 72 Z" fill="'+color+'" opacity="0.9"/>';
        break;
      case 'bob':
        s += '<path d="M20 38 Q20 18 50 14 Q80 18 80 38 L80 55 Q75 62 70 55 L70 40 Q70 28 50 24 Q30 28 30 40 L30 55 Q25 62 20 55 Z" fill="'+color+'"/>';
        break;
    }
    return s;
  }

  // ── Hair front layer ──
  function buildHairFront(style, color, dark, light, gender) {
    var s = '';
    switch(style) {
      case 'short-parted':
        s += '<path d="M24 38 Q24 18 50 14 Q76 18 76 38 L72 35 Q68 22 50 20 Q32 22 28 35 Z" fill="'+color+'"/>';
        s += '<path d="M42 16 Q50 13 58 16 L55 19 Q50 17 45 19 Z" fill="'+light+'" opacity="0.3"/>';
        break;
      case 'short-messy':
        s += '<path d="M24 38 Q22 16 50 12 Q78 16 76 38 L74 32 Q70 18 50 16 Q30 18 26 32 Z" fill="'+color+'"/>';
        s += '<path d="M35 14 L38 18 L33 16 Z" fill="'+color+'"/>';
        s += '<path d="M60 13 L65 17 L58 16 Z" fill="'+color+'"/>';
        s += '<path d="M48 12 L52 10 L50 15 Z" fill="'+dark+'"/>';
        break;
      case 'short-fade':
        s += '<path d="M26 40 Q26 22 50 17 Q74 22 74 40 L72 36 Q70 24 50 21 Q30 24 28 36 Z" fill="'+color+'"/>';
        s += '<rect x="24" y="38" width="6" height="10" rx="2" fill="'+color+'" opacity="0.4"/>';
        s += '<rect x="70" y="38" width="6" height="10" rx="2" fill="'+color+'" opacity="0.4"/>';
        break;
      case 'short-neat':
        s += '<path d="M25 38 Q25 19 50 15 Q75 19 75 38 L73 34 Q70 22 50 19 Q30 22 27 34 Z" fill="'+color+'"/>';
        break;
      case 'buzz':
        s += '<path d="M25 42 Q25 22 50 17 Q75 22 75 42 L73 38 Q70 25 50 22 Q30 25 27 38 Z" fill="'+color+'" opacity="0.6"/>';
        break;
      case 'long-wavy':
        s += '<path d="M22 38 Q22 15 50 10 Q78 15 78 38 L75 32 Q72 18 50 15 Q28 18 25 32 Z" fill="'+color+'"/>';
        s += '<path d="M25 32 Q28 28 32 32 Q36 36 40 32" stroke="'+light+'" stroke-width="1" fill="none" opacity="0.3"/>';
        break;
      case 'long-straight':
        s += '<path d="M22 38 Q22 15 50 10 Q78 15 78 38 L75 32 Q72 18 50 15 Q28 18 25 32 Z" fill="'+color+'"/>';
        break;
      case 'long-curly':
        s += '<path d="M20 38 Q20 12 50 8 Q80 12 80 38 L76 30 Q72 16 50 13 Q28 16 24 30 Z" fill="'+color+'"/>';
        // Curly tendrils
        s += '<circle cx="22" cy="42" r="4" fill="'+color+'"/>';
        s += '<circle cx="78" cy="42" r="4" fill="'+color+'"/>';
        s += '<circle cx="20" cy="50" r="3" fill="'+color+'"/>';
        s += '<circle cx="80" cy="50" r="3" fill="'+color+'"/>';
        break;
      case 'bob':
        s += '<path d="M22 38 Q22 16 50 12 Q78 16 78 38 L76 33 Q72 20 50 17 Q28 20 24 33 Z" fill="'+color+'"/>';
        // Bangs
        s += '<path d="M30 30 Q35 25 40 28 Q45 22 50 26 Q55 22 60 28 Q65 25 70 30" fill="'+color+'" stroke="'+dark+'" stroke-width="0.5"/>';
        break;
      case 'pixie':
        s += '<path d="M24 40 Q24 18 50 13 Q76 18 76 35 L73 30 Q70 20 50 17 Q30 20 27 32 Z" fill="'+color+'"/>';
        s += '<path d="M24 35 Q20 30 26 25 L30 30 Z" fill="'+color+'"/>';
        break;
      case 'ponytail':
        s += '<path d="M24 38 Q24 17 50 13 Q76 17 76 38 L73 33 Q70 21 50 18 Q30 21 27 33 Z" fill="'+color+'"/>';
        // Ponytail showing behind
        s += '<ellipse cx="72" cy="28" rx="6" ry="10" fill="'+color+'" transform="rotate(20, 72, 28)"/>';
        break;
      case 'bun':
        s += '<path d="M24 38 Q24 17 50 13 Q76 17 76 38 L73 33 Q70 21 50 18 Q30 21 27 33 Z" fill="'+color+'"/>';
        s += '<circle cx="50" cy="14" r="8" fill="'+color+'"/>';
        s += '<circle cx="50" cy="14" r="5" fill="'+dark+'" opacity="0.3"/>';
        break;
      case 'beanie':
        s += '<path d="M22 38 Q22 17 50 12 Q78 17 78 38 L76 34 Q72 20 50 16 Q28 20 24 34 Z" fill="#555"/>';
        s += '<rect x="22" y="34" width="56" height="6" rx="2" fill="#666"/>';
        s += '<circle cx="50" cy="10" r="3" fill="#555"/>';
        break;
      default:
        s += '<path d="M25 38 Q25 20 50 16 Q75 20 75 38 L73 35 Q70 23 50 20 Q30 23 27 35 Z" fill="'+color+'"/>';
    }
    return s;
  }

  // ── Accessory ──
  function buildAccessory(type, accent, hairColor) {
    var s = '';
    switch(type) {
      case 'glasses-round':
        s += '<circle cx="38" cy="42" r="10" fill="none" stroke="#555" stroke-width="1.8"/>';
        s += '<circle cx="62" cy="42" r="10" fill="none" stroke="#555" stroke-width="1.8"/>';
        s += '<line x1="48" y1="42" x2="52" y2="42" stroke="#555" stroke-width="1.5"/>';
        s += '<line x1="28" y1="42" x2="22" y2="40" stroke="#555" stroke-width="1.2"/>';
        s += '<line x1="72" y1="42" x2="78" y2="40" stroke="#555" stroke-width="1.2"/>';
        break;
      case 'glasses-square':
        s += '<rect x="29" y="36" width="18" height="13" rx="2" fill="none" stroke="#444" stroke-width="1.8"/>';
        s += '<rect x="53" y="36" width="18" height="13" rx="2" fill="none" stroke="#444" stroke-width="1.8"/>';
        s += '<line x1="47" y1="42" x2="53" y2="42" stroke="#444" stroke-width="1.5"/>';
        s += '<line x1="29" y1="40" x2="22" y2="38" stroke="#444" stroke-width="1.2"/>';
        s += '<line x1="71" y1="40" x2="78" y2="38" stroke="#444" stroke-width="1.2"/>';
        break;
      case 'glasses-cat':
        s += '<path d="M28 38 L29 36 Q38 32 47 38 L47 47 Q38 50 29 47 Z" fill="none" stroke="#666" stroke-width="1.5"/>';
        s += '<path d="M53 38 L53 36 Q62 32 71 38 L72 47 Q62 50 53 47 Z" fill="none" stroke="#666" stroke-width="1.5"/>';
        s += '<line x1="47" y1="42" x2="53" y2="42" stroke="#666" stroke-width="1.2"/>';
        break;
      case 'tie':
        s += '<path d="M46 78 L50 95 L54 78 Z" fill="'+accent+'"/>';
        s += '<path d="M46 76 L54 76 L53 79 L47 79 Z" fill="'+darken(accent,0.2)+'"/>';
        break;
      case 'bowtie':
        s += '<path d="M42 77 L50 80 L42 83 Z" fill="'+accent+'"/>';
        s += '<path d="M58 77 L50 80 L58 83 Z" fill="'+accent+'"/>';
        s += '<circle cx="50" cy="80" r="2" fill="'+darken(accent,0.2)+'"/>';
        break;
      case 'headphones':
        s += '<path d="M20 42 Q20 15 50 12 Q80 15 80 42" fill="none" stroke="#444" stroke-width="3.5" stroke-linecap="round"/>';
        s += '<rect x="15" y="38" width="8" height="14" rx="4" fill="#333" stroke="#555" stroke-width="1"/>';
        s += '<rect x="77" y="38" width="8" height="14" rx="4" fill="#333" stroke="#555" stroke-width="1"/>';
        break;
      case 'headset':
        s += '<path d="M22 42 Q22 18 50 14 Q78 18 78 42" fill="none" stroke="#555" stroke-width="2.5"/>';
        s += '<rect x="17" y="40" width="7" height="10" rx="3" fill="#444"/>';
        s += '<rect x="76" y="40" width="7" height="10" rx="3" fill="#444"/>';
        s += '<path d="M76 48 Q82 52 78 58 L80 60 Q86 52 78 46 Z" fill="#444"/>';
        break;
      case 'beret':
        s += '<ellipse cx="45" cy="18" rx="22" ry="8" fill="'+accent+'" transform="rotate(-5, 45, 18)"/>';
        s += '<circle cx="45" cy="12" r="2.5" fill="'+darken(accent,0.2)+'"/>';
        break;
      case 'earrings':
        s += '<circle cx="19" cy="56" r="2" fill="'+accent+'"/>';
        s += '<circle cx="81" cy="56" r="2" fill="'+accent+'"/>';
        break;
      case 'sweatband':
        s += '<path d="M24 32 Q24 30 28 29 Q50 26 72 29 Q76 30 76 32 L76 36 Q50 32 24 36 Z" fill="'+accent+'"/>';
        break;
      case 'star':
        s += '<text x="70" y="30" font-size="14" fill="'+accent+'" text-anchor="middle">✦</text>';
        break;
      case 'beard':
        s += '<path d="M30 55 Q30 68 50 72 Q70 68 70 55 Q65 60 50 62 Q35 60 30 55 Z" fill="'+hairColor+'" opacity="0.7"/>';
        break;
      case 'phone':
        s += '<rect x="72" y="52" width="8" height="14" rx="2" fill="#333" stroke="#555" stroke-width="0.8"/>';
        s += '<rect x="73.5" y="54" width="5" height="8" rx="1" fill="'+accent+'" opacity="0.5"/>';
        break;
      case 'stylus':
        s += '<line x1="75" y1="50" x2="82" y2="35" stroke="#888" stroke-width="1.5" stroke-linecap="round"/>';
        s += '<circle cx="82" cy="35" r="1.5" fill="'+accent+'"/>';
        break;
    }
    return s;
  }

  // ── Attire color ──
  function getAttireColor(attire, accent) {
    var map = {
      'suit-dark': '#1a1a2e', 'suit-grey': '#3a3a4a', 'hoodie': '#2d2d3d',
      'blazer': '#2a1a3a', 'blouse': '#1a2a3a', 'tshirt': '#252530',
      'shirt': '#1a2530', 'sweater': '#2a2535', 'cardigan': '#352a2a',
      'yoga': '#2a3530', 'professor': '#2a2520', 'athletic': '#25302a',
      'tactical': '#202525', 'artsy': '#352535', 'creative': '#30252a',
      'casual': '#2a2a35', 'bohemian': '#35302a'
    };
    return map[attire] || '#252530';
  }

  // ── Attire details (collar, neckline) ──
  function buildAttireDetails(attire, accent) {
    var s = '';
    switch(attire) {
      case 'suit-dark':
      case 'suit-grey':
        // Lapels
        s += '<path d="M35 78 L43 88 L38 95" fill="none" stroke="'+lighten(getAttireColor(attire, accent),0.2)+'" stroke-width="1.5"/>';
        s += '<path d="M65 78 L57 88 L62 95" fill="none" stroke="'+lighten(getAttireColor(attire, accent),0.2)+'" stroke-width="1.5"/>';
        // Shirt collar peek
        s += '<path d="M43 78 L50 84 L57 78" fill="#ddd" opacity="0.3"/>';
        break;
      case 'blazer':
        s += '<path d="M37 80 L44 90 L40 95" fill="none" stroke="'+lighten(getAttireColor(attire, accent),0.15)+'" stroke-width="1.2"/>';
        s += '<path d="M63 80 L56 90 L60 95" fill="none" stroke="'+lighten(getAttireColor(attire, accent),0.15)+'" stroke-width="1.2"/>';
        break;
      case 'hoodie':
        // Hood/drawstrings
        s += '<path d="M38 78 Q50 85 62 78" fill="none" stroke="'+lighten(getAttireColor(attire, accent),0.15)+'" stroke-width="1.5"/>';
        s += '<line x1="45" y1="82" x2="44" y2="90" stroke="#888" stroke-width="0.8"/>';
        s += '<line x1="55" y1="82" x2="56" y2="90" stroke="#888" stroke-width="0.8"/>';
        break;
      case 'tshirt':
        s += '<path d="M38 77 Q50 82 62 77" fill="none" stroke="'+lighten(getAttireColor(attire, accent),0.1)+'" stroke-width="1.2"/>';
        break;
      case 'shirt':
        // Collar
        s += '<path d="M42 77 L47 82 L50 78 L53 82 L58 77" fill="none" stroke="#888" stroke-width="1"/>';
        break;
    }
    return s;
  }

  // ═══════════════════════════════════════════════════════════════
  // ── PUBLIC API ───────────────────────────────────────────────
  // ═══════════════════════════════════════════════════════════════

  /**
   * Render an avatar into a container element
   * @param {string|HTMLElement} target - CSS selector or element
   * @param {string} slug - Agent slug
   * @param {object} opts - { size, expression, animate }
   */
  function render(target, slug, opts) {
    opts = opts || {};
    var el = (typeof target === 'string') ? document.querySelector(target) : target;
    if (!el) return;

    var size = opts.size || 80;
    var expr = opts.expression || 'neutral';
    var svg = buildSVG(slug, expr, size);
    el.innerHTML = svg;

    if (opts.animate !== false) {
      startIdleAnimation(el);
    }
  }

  /**
   * Get SVG string for an avatar (for inline use)
   */
  function getSVG(slug, expression, size) {
    return buildSVG(slug, expression || 'neutral', size || 80);
  }

  /**
   * Get mini avatar (for sidebar chat list, 28px)
   */
  function getMini(slug) {
    return buildSVG(slug, 'neutral', 28);
  }

  /**
   * Change expression on an existing avatar
   */
  function setExpression(container, slug, expression) {
    var el = (typeof container === 'string') ? document.querySelector(container) : container;
    if (!el) return;
    var size = 80;
    var existing = el.querySelector('svg');
    if (existing) size = parseInt(existing.getAttribute('width')) || 80;
    el.innerHTML = buildSVG(slug, expression, size);
    startIdleAnimation(el);
  }

  /**
   * Get profile data for a slug
   */
  function getProfile(slug) {
    return PROFILES[slug] || null;
  }

  /**
   * Get all available slugs
   */
  function getAllSlugs() {
    return Object.keys(PROFILES);
  }

  // ── Idle animation (blink every 3-6s) ──
  function startIdleAnimation(container) {
    var blinkEls = container.querySelectorAll('.avatar-blink');
    if (!blinkEls.length) return;

    function doBlink() {
      blinkEls.forEach(function(el) {
        el.style.transition = 'opacity 0.08s';
        el.style.opacity = '1';
        setTimeout(function() {
          el.style.opacity = '0';
        }, 120);
      });
      // Next blink
      setTimeout(doBlink, 3000 + Math.random() * 4000);
    }
    setTimeout(doBlink, 2000 + Math.random() * 3000);
  }

  // ── Expression cycle for "alive" effect ──
  function startExpressionCycle(container, slug, interval) {
    interval = interval || 8000;
    var expressions = ['neutral', 'smile', 'think', 'neutral', 'wink', 'smile', 'excited', 'neutral'];
    var idx = 0;
    setInterval(function() {
      idx = (idx + 1) % expressions.length;
      setExpression(container, slug, expressions[idx]);
    }, interval);
  }

  // ═══════════════════════════════════════════════════════════════
  // ── CONTEXTUAL GESTURE ENGINE ────────────────────────────────
  // Analyzes text tone/keywords → triggers micro-expressions,
  // head tilts, nods, reactions, and mood-based mimic changes
  // ═══════════════════════════════════════════════════════════════

  var GESTURES = {
    // Each gesture: expression + CSS animation class + duration
    greet:      { expr: 'smile',     anim: 'gesture-wave',      dur: 1200 },
    think:      { expr: 'think',     anim: 'gesture-tilt-left',  dur: 2000 },
    agree:      { expr: 'smile',     anim: 'gesture-nod',        dur: 800  },
    disagree:   { expr: 'serious',   anim: 'gesture-shake',      dur: 900  },
    surprise:   { expr: 'surprised', anim: 'gesture-jump',       dur: 600  },
    concern:    { expr: 'serious',   anim: 'gesture-tilt-right', dur: 1500 },
    celebrate:  { expr: 'smile',     anim: 'gesture-bounce',     dur: 1000 },
    confused:   { expr: 'surprised', anim: 'gesture-tilt-left',  dur: 1800 },
    listen:     { expr: 'neutral',   anim: 'gesture-lean-in',    dur: 2000 },
    excited:    { expr: 'smile',     anim: 'gesture-bounce',     dur: 700  },
    sad:        { expr: 'serious',   anim: 'gesture-droop',      dur: 2000 },
    focus:      { expr: 'think',     anim: 'gesture-lean-in',    dur: 1500 },
    laugh:      { expr: 'smile',     anim: 'gesture-shake',      dur: 600  },
    wink:       { expr: 'wink',      anim: 'gesture-nod',        dur: 900  },
    excited:    { expr: 'excited',   anim: 'gesture-bounce',     dur: 800  }
  };

  // Keyword → gesture mapping (ordered by priority)
  var GESTURE_RULES = [
    // Greetings
    { pattern: /\b(hello|hi|hey|salut|buna|howdy|greetings|welcome)\b/i, gesture: 'greet' },
    // Positive / celebration
    { pattern: /\b(congratulations|congrats|amazing|awesome|excellent|perfect|great job|bravo|fantastic|wonderful|superb)\b/i, gesture: 'celebrate' },
    { pattern: /\b(haha|lol|😂|🤣|funny|hilarious|lmao)\b/i, gesture: 'laugh' },
    { pattern: /\b(wink|😉|between us|secret|hint|psst|nudge)\b/i, gesture: 'wink' },
    { pattern: /(\!{2,}|🎉|🎊|🥳|🚀)/i, gesture: 'excited' },
    // Agreement
    { pattern: /\b(yes|da|correct|exactly|indeed|agree|sure|absolutely|definitely|right)\b/i, gesture: 'agree' },
    // Disagreement / negative
    { pattern: /\b(no|nu|wrong|incorrect|disagree|nope|not really|I don't think)\b/i, gesture: 'disagree' },
    { pattern: /\b(error|fail|bug|crash|broken|issue|problem|wrong)\b/i, gesture: 'concern' },
    { pattern: /\b(sorry|unfortunately|sad|bad news|regret|disappoint)/i, gesture: 'sad' },
    // Surprise
    { pattern: /\b(wow|whoa|really|seriously|no way|unbelievable|incredible|omg)\b/i, gesture: 'surprise' },
    { pattern: /(\?{2,}|😮|😲|🤯)/i, gesture: 'surprise' },
    // Thinking / analysis
    { pattern: /\b(think|analyze|consider|evaluate|review|assess|ponder|reflect|hmm|let me see)\b/i, gesture: 'think' },
    { pattern: /\b(how|why|what if|could we|should we|strategy|plan|approach)\b/i, gesture: 'think' },
    // Questions / confusion
    { pattern: /\b(confused|unclear|don't understand|what do you mean|huh|explain)\b/i, gesture: 'confused' },
    // Focus / important
    { pattern: /\b(important|critical|urgent|priority|focus|attention|key|essential)\b/i, gesture: 'focus' },
    // Listening / empathy
    { pattern: /\b(tell me|go on|I see|understand|interesting|continue|please share)\b/i, gesture: 'listen' }
  ];

  /**
   * Analyze text and return the best-matching gesture
   * @param {string} text - User or agent message text
   * @returns {object|null} - { gesture, expr, anim, dur } or null
   */
  function analyzeGesture(text) {
    if (!text || typeof text !== 'string') return null;

    // Strip HTML
    var clean = text.replace(/<[^>]+>/g, ' ').trim();
    if (!clean) return null;

    for (var i = 0; i < GESTURE_RULES.length; i++) {
      if (GESTURE_RULES[i].pattern.test(clean)) {
        var gName = GESTURE_RULES[i].gesture;
        var g = GESTURES[gName];
        return { gesture: gName, expr: g.expr, anim: g.anim, dur: g.dur };
      }
    }

    // Tone heuristics as fallback
    var questionMarks = (clean.match(/\?/g) || []).length;
    var exclamations = (clean.match(/!/g) || []).length;
    var caps = (clean.match(/[A-Z]{3,}/g) || []).length;

    if (questionMarks >= 2) return { gesture: 'confused', expr: 'surprised', anim: 'gesture-tilt-left', dur: 1500 };
    if (exclamations >= 2 || caps >= 2) return { gesture: 'excited', expr: 'smile', anim: 'gesture-bounce', dur: 700 };
    if (clean.length > 200) return { gesture: 'focus', expr: 'think', anim: 'gesture-lean-in', dur: 1500 };

    return null;
  }

  /**
   * Trigger a gesture reaction on an avatar container
   * @param {string|HTMLElement} container - CSS selector or element
   * @param {string} slug - Agent slug
   * @param {string} text - Text to analyze for gesture
   * @param {object} opts - { fallbackExpr, onComplete }
   */
  function gestureReact(container, slug, text, opts) {
    opts = opts || {};
    var el = (typeof container === 'string') ? document.querySelector(container) : container;
    if (!el) return;

    var result = analyzeGesture(text);
    if (!result) {
      // No gesture detected → subtle nod as acknowledgement
      result = { gesture: 'listen', expr: opts.fallbackExpr || 'neutral', anim: 'gesture-nod', dur: 600 };
    }

    // Change expression
    var size = 80;
    var existing = el.querySelector('svg');
    if (existing) size = parseInt(existing.getAttribute('width')) || 80;
    el.innerHTML = buildSVG(slug, result.expr, size);

    // Apply CSS animation
    var svg = el.querySelector('svg');
    if (svg) {
      svg.classList.add(result.anim);
      svg.classList.add('avatar-expression-swap');

      // Cleanup after gesture duration → return to neutral or fallback
      setTimeout(function() {
        svg.classList.remove(result.anim);
        // Return to rest after gesture
        setTimeout(function() {
          var restExpr = opts.fallbackExpr || 'neutral';
          el.innerHTML = buildSVG(slug, restExpr, size);
          startIdleAnimation(el);
          if (opts.onComplete) opts.onComplete(result);
        }, 400);
      }, result.dur);
    }

    return result;
  }

  return {
    render: render,
    getSVG: getSVG,
    getMini: getMini,
    setExpression: setExpression,
    getProfile: getProfile,
    getAllSlugs: getAllSlugs,
    startExpressionCycle: startExpressionCycle,
    analyzeGesture: analyzeGesture,
    gestureReact: gestureReact,
    PROFILES: PROFILES,
    GESTURES: GESTURES
  };

})();
