import { describe, it, expect } from 'vitest';
import { TRANSLATIONS, SupportedLanguage, translate } from './translations';

describe('i18n translation parity across EN, HI, TE, KN', () => {
  const languages: SupportedLanguage[] = ['hi', 'te', 'kn'];
  const enKeys = Object.keys(TRANSLATIONS.en);

  it('has non-empty translations for every English key across hi, te, kn', () => {
    expect(enKeys.length).toBeGreaterThan(50);
    for (const lang of languages) {
      const langKeys = Object.keys(TRANSLATIONS[lang]);
      const missing = enKeys.filter((k) => !langKeys.includes(k));
      expect(missing, `Missing keys for ${lang}`).toEqual([]);

      for (const k of enKeys) {
        const val = TRANSLATIONS[lang][k];
        expect(typeof val).toBe('string');
        expect(val.trim().length, `Empty value for ${lang}.${k}`).toBeGreaterThan(0);
        // Native scripts should actually translate non-badge strings (keep technical badges allowed)
        if (!['nav_live', 'badge_simulated_load', 'baseline_simulated_tag', 'alerts_demo_badge', 'source_cloudflare_radar'].includes(k)) {
          expect(val, `Untranslated copy for ${lang}.${k}`).not.toEqual(TRANSLATIONS.en[k]);
        }
      }
    }
  });

  it('interpolates variables and keeps Western digits', () => {
    const knHeading = translate('kn', 'attention_heading', { total: 4, overloaded: 2, weak: 2 });
    expect(knHeading).toContain('4');
    expect(knHeading).toContain('2');
    expect(knHeading).toContain('ಸೈಟ್');
  });
});

