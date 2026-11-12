import { describe, expect, it } from 'vitest';
import { renderMarkdown, stripMarkdown } from './text';

// The Transmodel import writes standard markdown links to concept anchors —
// the shape from Martin's "Access" screenshot.
const ACCESS_STYLE =
  'The walking movement from a [Place](#f3315928-c20f-4039-a4db-24f8837589fd) ' +
  'to a [Scheduled stop point](#3a4eb917-a26c-4bc5-a48b-faa53e57b81b).';

describe('renderMarkdown', () => {
  it('renders concept-anchor links as concept links', () => {
    const html = renderMarkdown(ACCESS_STYLE);
    expect(html).toContain('<a href="/concepts/f3315928-c20f-4039-a4db-24f8837589fd" class="crossref">Place</a>');
    expect(html).toContain('class="crossref">Scheduled stop point</a>');
    expect(html).not.toContain('](#');
  });

  it('renders external links safely', () => {
    const html = renderMarkdown('Se [UITP](https://uitp.org) för mer.');
    expect(html).toContain('<a href="https://uitp.org" target="_blank" rel="noopener noreferrer">UITP</a>');
  });

  it('keeps [[crossrefs]], bold and italic working alongside links', () => {
    const html = renderMarkdown('En **hållplats** med *läge*, se [[bytespunkt]] och [Plats](#abc).');
    expect(html).toContain('<strong>hållplats</strong>');
    expect(html).toContain('<em>läge</em>');
    expect(html).toContain('class="crossref">bytespunkt</a>');
    expect(html).toContain('/concepts/abc');
  });

  it('escapes HTML before linking', () => {
    expect(renderMarkdown('<script>x</script> [a](#b)')).toContain('&lt;script&gt;');
  });

  it('renders ## headings (the collection descriptions) with inline markup', () => {
    const html = renderMarkdown('## Bakgrund\n\nKollepedia skapades av **Transportidé AB**.');
    expect(html).toContain('<h2>Bakgrund</h2>');
    expect(html).toContain('<p>Kollepedia skapades av <strong>Transportidé AB</strong>.</p>');
    expect(html).not.toContain('## ');
  });

  it('renders bullet and numbered lists', () => {
    expect(renderMarkdown('- ett\n- två')).toBe('<ul><li>ett</li><li>två</li></ul>');
    expect(renderMarkdown('1. först\n2. sen')).toBe('<ol><li>först</li><li>sen</li></ol>');
  });

  it('keeps a heading and its following paragraph in one block', () => {
    const html = renderMarkdown('### Källa\nSe [UITP](https://uitp.org).');
    expect(html).toContain('<h3>Källa</h3>');
    expect(html).toContain('rel="noopener noreferrer">UITP</a>');
  });
});

describe('renderMarkdown link targets (stored-XSS guard, security review 2026-11-10 §4.1)', () => {
  it.each([
    ['javascript:', '[här](javascript:document.cookie)'],
    ['data:', '[bild](data:text/html;base64,PHNjcmlwdD5hbGVydCgxKTwvc2NyaXB0Pg==)'],
    ['vbscript:', '[x](vbscript:MsgBox)'],
    ['mixed-case javascript:', '[x](JavaScript:void0)'],
    ['file:', '[x](file:///etc/passwd)']
  ])('renders a %s target as plain text, never a link', (_scheme, md) => {
    const html = renderMarkdown(md);
    expect(html).not.toContain('<a');
    expect(html).not.toContain('href=');
    expect(html).toBe(`<p>${md}</p>`);
  });

  it('escapes a rejected target exactly once', () => {
    expect(renderMarkdown('[x](javascript:a&b)')).toBe('<p>[x](javascript:a&amp;b)</p>');
  });

  it.each([
    ['http://example.org/x', '<a href="http://example.org/x" target="_blank" rel="noopener noreferrer">x</a>'],
    ['https://example.org/x', '<a href="https://example.org/x" target="_blank" rel="noopener noreferrer">x</a>'],
    ['HTTPS://EXAMPLE.ORG/', '<a href="HTTPS://EXAMPLE.ORG/" target="_blank" rel="noopener noreferrer">x</a>'],
    ['//example.org/x', '<a href="//example.org/x" target="_blank" rel="noopener noreferrer">x</a>'],
    ['mailto:info@example.org', '<a href="mailto:info@example.org">x</a>'],
    ['/collections/transmodel', '<a href="/collections/transmodel">x</a>'],
    ['#abc-123', '<a href="/concepts/abc-123" class="crossref">x</a>']
  ])('still links %s', (target, anchor) => {
    expect(renderMarkdown(`se [x](${target})`)).toBe(`<p>se ${anchor}</p>`);
  });

  it('keeps escaping & < > " in text and link labels', () => {
    const html = renderMarkdown('Tom & Jerry <b> "citat" > [a&b](/x)');
    expect(html).toContain('Tom &amp; Jerry &lt;b&gt; &quot;citat&quot; &gt;');
    expect(html).toContain('<a href="/x">a&amp;b</a>');
    expect(html).not.toContain('<b>');
  });

  it('a quote inside an allowed target cannot break out of href', () => {
    expect(renderMarkdown('[x](/p"onmouseover=evil)')).toBe(
      '<p><a href="/p&quot;onmouseover=evil">x</a></p>'
    );
  });
});

describe('stripMarkdown (feeds the Time Machine diff)', () => {
  it('strips markdown links to their labels', () => {
    expect(stripMarkdown(ACCESS_STYLE)).toBe(
      'The walking movement from a Place to a Scheduled stop point.'
    );
  });

  it('a formatting-only change strips to identical text', () => {
    const plain = 'En hållplats är en plats där resenärer kliver på och av.';
    const formatted = 'En **hållplats** är en plats där resenärer kliver *på och av*.';
    expect(stripMarkdown(formatted)).toBe(stripMarkdown(plain));
  });
});
