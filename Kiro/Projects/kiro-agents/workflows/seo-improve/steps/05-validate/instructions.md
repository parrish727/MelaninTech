# Step: Validate

Run visual and performance validation on the preview deployment.

## Actions
1. Take screenshots at desktop/tablet/mobile via Playwright
2. Run Lighthouse audit (performance, accessibility, SEO scores)
3. Compare before/after screenshots for visual regression
4. Check that Lighthouse scores don't drop below thresholds:
   - Performance ≥ 70
   - Accessibility ≥ 85
   - SEO ≥ 80
5. Post results to Slack with approve/reject buttons

## Pass Criteria
- No Lighthouse regressions
- Visual diff < 15% (cosmetic changes are expected)
- All breakpoints render without layout breaks
