# SL_Heaven Integration Plan — Energy Audit Lite

> **Status:** Research & Planning (2026-03-23)
> **Branch:** N/A — planning only, no code changes yet
> **Reference apps:** Asset Planner (EWEM), Carbon Performance, QIP (AI integration)

---

## Table of Contents

1. [Overview](#overview)
2. [SL_Heaven App Deployment Pattern](#sl_heaven-app-deployment-pattern)
3. [Frontend Architecture](#frontend-architecture)
4. [API Integration Pattern (QIP Reference)](#api-integration-pattern-qip-reference)
5. [Storage Layer — EWEM Tables](#storage-layer--ewem-tables)
6. [Carbon Performance Bridge](#carbon-performance-bridge)
7. [ESPM Target Finder Integration](#espm-target-finder-integration)
8. [Project Scope Type — "Rapid Energy Audit"](#project-scope-type--rapid-energy-audit)
9. [Navigation Integration](#navigation-integration)
10. [Dependency Considerations](#dependency-considerations)
11. [Architecture Diagram](#architecture-diagram)
12. [Remaining Open Items](#remaining-open-items)
13. [Key File References](#key-file-references)

---

## Overview

Port the Energy Audit Lite application into SL_Heaven following existing integration patterns. The Python FastAPI backend stays as a separate service (deployed on AWS Docker, similar to QIP). The Vue frontend is rebuilt as SL_Heaven page components mounted via the `data-app` pattern. Assessment results are stored as EWEM records to enable future import into Carbon Performance.

### Decisions Made

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Backend architecture | Python stays separate, Rails proxies via Sidekiq | Matches QIP pattern (latest integration) |
| Assessment storage | EWEM table rows | Enables Carbon Performance import |
| Project scope type | New "Rapid Energy Audit" scope | Follows existing scope pattern |
| ESPM Target Finder | Extend existing `EnergyStarPortfolioManager` model | Reuses credentials + HTTP wrapper |
| 3D building map | MapLibre GL (add to SL_Heaven) | Required feature |
| Assessment tied to | Existing project scopes | Per user requirement |
| CSS framework | Tailwind CSS (via partner-components merge) | Partner-components brings Tailwind into the build chain; no style rewrite needed |
| Component library | Partner-components (`@partnerdevops/partner-components`) | Wait for `feature-partner-components-attempt-2` to merge, then build on it |
| TypeScript | Convert to JavaScript | SL_Heaven has no TS tooling; composables convert to .js |

---

## SL_Heaven App Deployment Pattern

SL_Heaven uses a **minimal-ERB + data-app auto-mounting** pattern. There is no Vue Router — Rails handles all routing, and each page is an independent Vue 3 instance.

### The 4-File Pattern

To add a new app, you create four things:

| Layer | File | Example (Asset Planner) |
|-------|------|------------------------|
| **Route** | `config/routes.rb` | `get :asset_planner` under `resources :ewems` |
| **Controller** | `app/controllers/partner_esg/ewems_controller.rb` | `#asset_planner` action — loads project, renders view |
| **ERB View** | `app/views/partner_esg/ewems/asset_planner.html.erb` | `<div data-app='partner_energy/carbon_performance/AssetPlanner'></div>` |
| **Vue Page** | `app/vue_frontend/javascript/pages/.../AssetPlanner.vue` | Full Vue 3 component |

### Auto-Mounting System

The Vite entrypoint (`app/vue_frontend/entrypoints/application.js`) handles mounting automatically:

1. Uses `import.meta.glob('../javascript/pages/**/*.vue')` for lazy component discovery
2. On page load, scans DOM for `[data-app]` elements
3. Resolves component path from the `data-app` attribute value
4. Converts `data-*` attributes to camelCase props (with JSON parsing)
5. Calls `createApp(Component, props).mount(el)` for each element

**No manual registration needed.** Just drop a `.vue` file in `pages/` and reference it from an ERB view.

### Props Passing

```erb
<!-- Rails view passes data via HTML data attributes -->
<div data-app='partner_energy/energy_assessment/EnergyAssessment'
     data-project-id='<%= @project.id %>'
     data-project-scope-id='<%= @project_scope.id %>'>
</div>
```

The `datasetToProps` function in `application.js` converts `data-project-id` to `projectId` prop automatically.

---

## Frontend Architecture

### Build System

| Aspect | Detail |
|--------|--------|
| **Bundler** | Vite 6.4 (`vite-plugin-ruby` for Rails integration) |
| **Vue** | 3.3.x (Composition API or Options API) |
| **Routing** | Rails only — no Vue Router |
| **State management** | Local component `data()` + composables — no Pinia/Vuex |
| **API calls** | Direct `axios` to relative paths |
| **Auth** | Rails session cookies (no JWT) |
| **CSRF** | Auto via `meta[name="csrf-token"]` tag |
| **Charts** | Highcharts (`highcharts-vue`) |
| **TypeScript** | Not configured — all `.vue` files use JavaScript |

### File Structure Convention

```
app/vue_frontend/
├── entrypoints/
│   └── application.js              # Main Vite entry, auto-mounts data-app elements
├── javascript/
│   ├── pages/                       # Full-page components (mapped to Rails views)
│   │   └── partner_energy/
│   │       └── energy_assessment/
│   │           └── EnergyAssessment.vue
│   ├── components/                  # Reusable sub-components
│   │   └── energy_assessment/
│   │       ├── BuildingForm.vue
│   │       ├── AssessmentResults.vue
│   │       ├── MeasureTable.vue
│   │       └── BuildingMapViewer.vue
│   ├── helpers/                     # Utility functions
│   │   └── energyAssessmentHelper.js
│   └── utils/                       # Global singletons (mixpanel, toast, etc.)
└── assets/                          # Static images/logos
```

### Vite Config

```typescript
// vite.config.ts
import { defineConfig } from 'vite'
import RubyPlugin from 'vite-plugin-ruby'
import FullReload from 'vite-plugin-full-reload'
import vue from '@vitejs/plugin-vue'
import svgLoader from 'vite-svg-loader'

export default defineConfig({
  build: { sourcemap: false },
  plugins: [
    RubyPlugin(),
    FullReload(['config/routes.rb', 'app/views/**/*']),
    vue(),
    svgLoader()
  ],
  optimizeDeps: { include: ['pdfjs-dist'] },
})
```

### Layout Inclusion

```erb
<!-- app/views/layouts/application.html.erb -->
<%= vite_client_tag %>
<%= vite_javascript_tag 'application' %>
```

### Partner Components Status

A feature branch exists: `remotes/origin/feature-partner-components-attempt-2`

- Adds `@partnerdevops/partner-components` v0.0.20 via GitHub Packages
- Adds `pinia` v3.0.4 and `reka-ui` v2.9.1 (transitive)
- Includes NPM token auth infrastructure (`bin/npm-with-env`, `.npmrc`)
- Has working test page at `/admin/partner_components_test`
- **Not merged to main** — status TBD with SiteLynx team

---

## API Integration Pattern (QIP Reference)

The QIP (AI integration) is the latest example of SL_Heaven calling an external Python API. This is the pattern to follow.

### Architecture

```
Vue Component
  → POST /project_scopes/:id/execute_ai_resource_job_for_project_scope
    → Rails controller creates BackgroundJob (status: queued) + AiJob record
    → Enqueues Sidekiq job (AiResourceJob, queue: ai_processing)
      → Net::HTTP POST to Python API (Bearer token, 90s timeout)
      → If sync response: saves to AiJobResponse, marks BackgroundJob completed
      → If async (status: "queued"): PartnerAiPollingJob polls status_url every 20-30s
  → Vue polls GET /project_scopes/:id/ai_action_result every 10s
  → On completion: renders result
```

### HTTP Client Details

- **Library:** Ruby `Net::HTTP` (not HTTParty or Faraday)
- **Auth:** Bearer token from `Rails.application.credentials.ai[provider_key]`
- **API URL:** Stored in `ai_resources` DB table
- **Timeouts:** 90s read/write
- **Retries:** Sleep 10-30s + re-enqueue on 429/500/timeout
- **Response storage:** Full JSON in `ai_job_responses.response` (LONGTEXT)

### Job Tracking

| Table | Purpose |
|-------|---------|
| `background_jobs` | Status lifecycle: queued → running → completed/failed/cancelled |
| `ai_jobs` | Links use case config + resource + request body |
| `ai_job_responses` | Stores each HTTP response (status code + body) |

### Adaptation for Energy Assessment

For `/assess` (the main assessment endpoint), follow the async pattern:

| Endpoint | Latency | Approach |
|----------|---------|----------|
| `POST /assess` | 2-30s (model loading on cold start) | **Async via Sidekiq** |
| `GET /lookup` | 1-3s | Sync Rails proxy |
| `GET /autocomplete` | <1s | Sync Rails proxy |
| `GET /metadata` | <1s | Sync Rails proxy (cacheable) |

We can potentially simplify to sync later if cloud latency proves consistently fast.

---

## Storage Layer — EWEM Tables

Assessment results are stored as `ewems` table rows. This enables future import into Carbon Performance and Asset Planner.

### Column Mapping: Assessment Output → EWEM

| Assessment Output | EWEM Column | Type |
|-------------------|-------------|------|
| Measure name/description | `description` | text |
| Electricity savings (kWh) | `annual_site_energy_savings_total_electricity` | decimal 13,2 |
| Gas savings (therms) | `annual_site_energy_savings_total_gas` | decimal 13,2 |
| Electricity cost savings ($) | `annual_cost_savings_total_electricity` | decimal 13,2 |
| Gas cost savings ($) | `annual_cost_savings_total_gas` | decimal 13,2 |
| Installed cost ($) | `installed_cost` / `premium_cost` | decimal 13,2 |
| Standard/baseline cost ($) | `standard_cost` | decimal 13,2 |
| Rebate/incentive ($) | `rebate` | decimal 10,2 |
| O&M savings ($) | `o_m_savings` | decimal 13,2 |
| Gross payback (years) | `gross_payback` | decimal 10,2 |
| Net payback (years) | `net_payback` | decimal 10,2 |

### Classification Columns

| Column | Value for Our Tool |
|--------|-------------------|
| `source` | `"Energy Audit"` (accepted value) |
| `project_type` | `"Energy Efficiency"` or `"Electrification"` per measure |
| `system_type` | Broad category: "Mechanical, Electrical, Plumbing, FLS", "Electrical", "Building Envelope" |
| `subcomponent` | Detailed: "HVAC", "Lighting", "Windows", etc. |
| `status` | `"Identified"` (default) |
| `cost_category` | `"Immediate"`, `"Short Term"`, `"Reserve"` |
| `include_in_carbon_performance` | `true` — **critical flag for Carbon Performance integration** |
| `fuel_switching` | `true` for electrification measures |
| `priority` | `"Low"`, `"Medium"`, `"High"` |

### What Our Assessment Produces That EWEMs Don't Have

| Data Point | Where It Goes |
|------------|--------------|
| Baseline EUI by fuel | `baseline_metrics` table (not EWEM) |
| Measure applicability (yes/no) | Only create EWEMs for applicable measures |
| NREL measure description text | `description` or `additional_notes` column |
| Post-upgrade EUI | Derived by Carbon Performance from baseline - savings |
| CO2e reduction | Calculated by Carbon Performance using eGRID factors |
| ENERGY STAR projected score | Separate — stored via Target Finder results |

### EWEM Model Details

```ruby
# app/models/ewem.rb
class Ewem < ApplicationRecord
  belongs_to :project
  has_one :energy_efficiency_measure, dependent: :destroy
end
```

- **Paper Trail versioning** — all changes tracked
- **Soft delete** — `deprecated: true` (not hard delete)
- **Parent/child hierarchy** — `parent_ewem_id` for grouping
- **Auto-calculated payback** — `update_payback_values` method

---

## Carbon Performance Bridge

Each EWEM with `include_in_carbon_performance: true` gets a 1:1 `energy_efficiency_measure` record.

### EnergyEfficiencyMeasure Table (Bridge)

Key columns Carbon Performance uses:

| Column | Purpose |
|--------|---------|
| `ewem_id` | FK to parent EWEM |
| `cost` | Total installed cost |
| `net_installed_cost` | After deducting standard cost + rebate |
| `cost_savings` | Annual total cost savings (all fuels + O&M) |
| `kwh_savings` | Annual electricity savings |
| `therm_savings` | Annual gas savings |
| `year_implemented` | When measure takes effect |
| `spread_years` | Years to spread cost/savings over |
| `degradation` | Annual degradation % (for renewables) |
| `partial_measure` | % of measure applied (1-100) |
| `bool_active` | Whether included in current scenario |

### How Carbon Performance Reads These

```ruby
# Only includes EWEMs where:
#   include_in_carbon_performance: true
#   deprecated: false
#   status != 'Not Approved'
EnergyEfficiencyMeasure.get_by_baseline_metric_id(baseline_metric_id)
```

Carbon Performance then loops through each year (baseline → 2050):
1. Sums electricity savings (kWh) across all EE measures
2. Sums gas savings (therms) across all EE measures
3. Applies spread_years and degradation factors
4. Calculates post-measure electric/gas consumption
5. Converts to CO2e using eGRID emission factors
6. Produces year-by-year projections for charts

**This means:** Once our audit results are saved as EWEMs with `include_in_carbon_performance: true`, Carbon Performance automatically incorporates them into decarbonization projections with zero additional work.

---

## ESPM Target Finder Integration

### Current ESPM Integration in SL_Heaven

SL_Heaven has a comprehensive ESPM integration for **consumption data** but does **NOT** implement the Target Finder API.

**What exists:**
- `EnergyStarPortfolioManager` model — HTTP wrapper with retry/rate-limit handling
- Basic Auth via `Rails.application.credentials.energy_star[:P_M_USERNAME]` and `[:P_M_PASSWORD]`
- Property, meter, and consumption endpoints
- Daily sync via Sidekiq scheduler
- Rate limiting: retry on 429 with 1s then 2s delay

**API endpoints currently used:**
- `account/{id}/property/list` — Property listing
- `property/{id}` — Property details
- `property/{id}/metrics` — Monthly metrics (score, EUI, GHG, costs)
- `property/{id}/meter/list` — Meter listing
- `meter/{id}/consumptionData` — Monthly consumption

**What does NOT exist:**
- Target Finder API calls
- Score prediction/projection

### Recommendation: Extend Existing Model

Add Target Finder methods to `EnergyStarPortfolioManager`:

```ruby
# Reuses existing credentials, HTTP wrapper, and rate-limit handling
def target_finder_score(building_params)
  # POST to Target Finder endpoint
  # Returns projected ENERGY STAR score
end
```

This keeps all ESPM API calls in one place with shared auth and error handling.

---

## Project Scope Type — "Rapid Energy Audit"

### How Scope Types Work

Scope types are **NOT stored in the database**. They are dynamically detected by pattern-matching against the `name` and `scope_description` fields (case-insensitive substring match) in the `ProjectScope#project_scope_type` method.

There are currently 19 recognized scope types detected via an `if/elsif` chain.

### Changes Required to Add "Rapid Energy Audit"

**1. `ProjectScope#project_scope_type`** (`app/models/project_scope.rb`, line ~483)

Add an `elsif` clause to the detection chain:
```ruby
elsif name_and_description.include?('rapid energy audit')
  'rapid energy audit'
```

**2. `Project` model** (`app/models/project.rb`, line ~1329)

Add helper method:
```ruby
def return_all_rapid_energy_audit_scopes
  project_scopes.select { |s| s.name_and_description.include?('rapid energy audit') }
end
```

Update `has_energy_scope?` to include the new type.

**3. `EnergyPortfolio` model** — Programmatic scope creation

Follow the `create_carbon_performance_scope` pattern:
```ruby
def self.create_rapid_energy_audit_scope(project, user_id)
  return if project.return_all_rapid_energy_audit_scopes.any?
  workscope = Workscope.find_by(name: 'Rapid Energy Audit')
  return if workscope.nil?
  # Create ProjectScope with name/description = 'Rapid Energy Audit'
end
```

**4. Workscope seed record** — Insert `"Rapid Energy Audit"` into `workscopes` table.

---

## Navigation Integration

### Current Energy Section Structure

```erb
<!-- _navigation_3.html.erb -->
<% if @project&.has_energy_scope? %>
  <!-- Carbon Performance tabs -->
  <!-- Energy Compliance tabs -->
  <!-- Utility Benchmarking tabs -->
<% end %>

<% if @project&.return_all_asset_planner_scopes.present? %>
  <!-- Asset Planner tab -->
<% end %>
```

### Adding Rapid Energy Audit Tab

```erb
<% if @project&.return_all_rapid_energy_audit_scopes.present? %>
  <li>
    <%= link_to 'Rapid Energy Audit',
        energy_assessment_path(project_id: @project.id,
                               project_scope_id: scope.id),
        class: @energy_assessment_tab_class %>
  </li>
<% end %>
```

The tab appears conditionally — only when a project has a scope with "rapid energy audit" in its name/description.

---

## Dependency Considerations

### New Dependencies to Add to SL_Heaven

| Package | Purpose | Notes |
|---------|---------|-------|
| `maplibre-gl` | 3D building map viewer | Not currently in SL_Heaven |

### Style System — Tailwind CSS

**Decision:** Wait for partner-components to merge to main, then use Tailwind directly.

SL_Heaven historically uses scoped CSS + global SCSS. It does not have Tailwind installed. However, the partner-components library (`@partnerdevops/partner-components`) is built with Tailwind CSS 4 internally and ships a pre-compiled CSS file (`dist/partner-components.css`, ~91KB) containing all the Tailwind utilities its components need.

Once partner-components merges to SL_Heaven main (via `feature-partner-components-attempt-2` branch), Tailwind is effectively already in the build chain. At that point, adding `@tailwindcss/vite` as a first-class Vite plugin is a natural next step — it formalizes what's already present and avoids duplicating pre-compiled CSS.

**What this means for our app:**
- **No style conversion needed.** Our Vue components can keep their Tailwind utility classes as-is.
- **Dependency:** Partner-components must be merged first. This is a hard prerequisite.
- **TypeScript → JavaScript conversion** is still needed (SL_Heaven has no TS tooling). Convert `.ts` composables/types to `.js`.
- **Composables** (`useAssessment.ts` → `useAssessment.js`) work fine in SL_Heaven — no conflict with the local state pattern.

### How Partner-Components CSS Works

The partner-components library uses Tailwind as an *authoring tool* during its build step. The published npm package ships a finished, pre-compiled CSS file. Consumers (like SL_Heaven) just import it:

```javascript
// in application.js entrypoint
import '@partnerdevops/partner-components/dist/partner-components.css';
```

SL_Heaven doesn't need Tailwind installed to use partner-components — the CSS is already compiled. But for *our own* template utility classes (layout, spacing, flex, grid), we need Tailwind in the build. Once partner-components merges and establishes the precedent, adding the Vite plugin is a one-line change:

```typescript
// vite.config.ts — add to plugins array
import tailwindcss from '@tailwindcss/vite'
// ...
plugins: [RubyPlugin(), vue(), tailwindcss(), ...]
```

### Shared SL_Heaven Components Available

In addition to partner-components, SL_Heaven has built-in components:
- `CollapsibleSection.vue` — Expandable panels
- `Dropdown.vue` — Custom dropdowns
- `Paginate.vue` — Pagination
- Various icon components in `components/icons/`
- Helper utilities: `numberHelper.js`, `chartHelper.js`, `textHelper.js`

---

## Architecture Diagram

```
┌──────────────────────────────────────────────────────────────┐
│ SL_Heaven (Rails + Vue 3 + Vite)                             │
│                                                              │
│  ProjectScope "Rapid Energy Audit"                           │
│       │                                                      │
│       ▼                                                      │
│  EnergyAssessmentsController (Rails)                         │
│    ├── index        → renders Vue page (data-app mount)      │
│    ├── assess       → Sidekiq async → Python API /assess     │
│    ├── lookup       → sync proxy → Python API /lookup        │
│    ├── autocomplete → sync proxy → Python API /autocomplete  │
│    └── result       → polls BackgroundJob status             │
│                                                              │
│  Results stored as EWEMs:                                    │
│    ewems (source: "Energy Audit")                            │
│      └── energy_efficiency_measures (1:1)                    │
│            └── include_in_carbon_performance: true            │
│                    │                                         │
│                    ▼                                         │
│  Carbon Performance reads these measures                     │
│  → DecarbonizationGoalResult projections through 2050        │
│                                                              │
│  ESPM Target Finder (extend EnergyStarPortfolioManager):     │
│    → Same credentials, same HTTP wrapper                     │
│    → Returns projected ENERGY STAR score                     │
│                                                              │
│  Vue Frontend (auto-mounted via data-app):                   │
│    pages/partner_energy/energy_assessment/                    │
│      EnergyAssessment.vue                                    │
│    components/energy_assessment/                              │
│      BuildingForm, AssessmentResults, MeasureTable,          │
│      BuildingMapViewer (maplibre-gl)                         │
└──────────────────────────────────────────────────────────────┘
         │
         │ Net::HTTP (Bearer token, Sidekiq async for /assess)
         ▼
┌──────────────────────────────────────┐
│ Python FastAPI (AWS Docker)          │
│  POST /assess    — main assessment   │
│  GET  /lookup    — address geocoding │
│  GET  /autocomplete — address search │
│  GET  /metadata  — building types    │
│  XGBoost models (~462 .pkl files)    │
└──────────────────────────────────────┘
```

---

## Remaining Open Items

### Decided

- [x] **Partner-components** — Wait for `feature-partner-components-attempt-2` to merge to main, then build on it. Hard prerequisite.
- [x] **Tailwind CSS** — Use Tailwind directly. Partner-components merge brings it into the build chain; add `@tailwindcss/vite` plugin. No style rewrite.
- [x] **TypeScript** — Convert `.ts` files to `.js`. SL_Heaven has no TS support.

### Needs Decision

- [ ] **Map tile provider** — MapLibre needs a tile source. Is there an existing map tile service/key in SL_Heaven infrastructure?

### Needs Further Research

- [ ] **Python API deployment** — AWS Docker infrastructure details (similar to QIP deployment)
- [ ] **Baseline metrics integration** — Should we create/update a `baseline_metrics` record alongside EWEMs? This would enable tighter Carbon Performance integration.
- [ ] **EWEM system_type / subcomponent mapping** — Map our NREL upgrade categories to SL_Heaven's `EWEM_SYSTEM_TYPE_OPTIONS` and `EWEM_SUBCOMPONENT_OPTIONS` constants
- [ ] **Assessment result caching** — Store full assessment JSON (like QIP stores in `ai_job_responses`) in addition to EWEM records?
- [ ] **Multi-property assessments** — Can one "Rapid Energy Audit" scope cover multiple properties, or is it 1:1?

---

## Key File References

### SL_Heaven Codebase

| Component | Path |
|-----------|------|
| **Vite entrypoint (auto-mount)** | `app/vue_frontend/entrypoints/application.js` |
| **Vite config** | `vite.config.ts` |
| **Layout (includes Vite tags)** | `app/views/layouts/application.html.erb` |
| **Navigation partial** | `app/views/layouts/partials/_navigation_3.html.erb` |
| **Package.json** | `package.json` |
| **Routes** | `config/routes.rb` |
| **EWEM controller** | `app/controllers/partner_esg/ewems_controller.rb` |
| **EWEM model** | `app/models/ewem.rb` |
| **EWEM constants** | `app/helpers/constants/ewem_constants_helper.rb` |
| **EnergyEfficiencyMeasure model** | `app/models/energy_efficiency_measure.rb` |
| **Carbon Performance controller** | `app/controllers/partner_esg/decarbonization_goal_results_controller.rb` |
| **Carbon Performance calculations** | `app/models/decarbonization_goal_result.rb` |
| **ESPM API model** | `app/models/energy_star_portfolio_manager.rb` |
| **ESPM property model** | `app/models/energy_star_database/espm_property.rb` |
| **Baseline metrics model** | `app/models/baseline_metric.rb` |
| **ProjectScope model** | `app/models/project_scope.rb` |
| **Project model (scope helpers)** | `app/models/project.rb` |
| **EnergyPortfolio (scope creation)** | `app/models/energy_portfolio.rb` |
| **QIP Sidekiq job** | `app/sidekiq/ai_resource_job.rb` |
| **QIP job v3 (HTTP calls)** | `app/sidekiq/ai_resource_job_versions/ai_resource_job_v3.rb` |
| **QIP polling job** | `app/sidekiq/partner_ai_polling_job.rb` |
| **QIP Vue modal** | `app/vue_frontend/javascript/components/AiActionModal.vue` |
| **BackgroundJob model** | `app/models/background_job.rb` |
| **Asset Planner Vue page** | `app/vue_frontend/javascript/pages/partner_energy/carbon_performance/AssetPlanner.vue` |
| **Asset Planner ERB** | `app/views/partner_esg/ewems/asset_planner.html.erb` |
| **Carbon Performance Vue** | `app/vue_frontend/javascript/pages/partner_energy/carbon_performance/CarbonPerformance.vue` |
| **Partner-components branch** | `remotes/origin/feature-partner-components-attempt-2` |
| **DB schema** | `db/schema.rb` |

### Energy Audit Lite Codebase (This Repo)

| Component | Path |
|-----------|------|
| **Backend API routes** | `backend/app/api/routes.py` |
| **Assessment orchestrator** | `backend/app/services/assessment.py` |
| **Preprocessor** | `backend/app/services/preprocessor.py` |
| **Cost calculator** | `backend/app/services/cost_calculator.py` |
| **Emissions calculator** | `backend/app/services/emissions.py` |
| **Model manager** | `backend/app/inference/model_manager.py` |
| **Vue building form** | `frontend/src/components/BuildingForm.vue` |
| **Vue composable** | `frontend/src/composables/useAssessment.ts` |
| **Vue types** | `frontend/src/types/assessment.ts` |
| **Map viewer** | `frontend/src/components/BuildingMapViewer.vue` |
