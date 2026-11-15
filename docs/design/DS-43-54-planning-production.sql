-- DS-43 and DS-51 to DS-55 planning and production: DDL draft for ADR-0024 (planning), ADR-0033 (production master
-- data), ADR-0034 (production orders and shop floor), ADR-0035 (production costing), ADR-0036 (multi-level MRP) and
-- ADR-0037 (subcontracting), with the columns ADR-0046 rules 12-14 add to production structures and estimates, and the
-- holistic review decisions of 2026-11-15 (one operation_progress_component table, costing_lot_quantity, the B3
-- columns as an interim, the forecast, message and exception tables). PostgreSQL 18. Loaded with DS-20, DS-56, DS-15
-- and DS-06 in the design lab (docs/reviews/2026-11-14-design-validation, t16_planning_production_ddl.py). The ADRs
-- win if this file disagrees.
-- Conventions as DS-20: tables in schema erpme, domains in types; keys inline (migrations name them by the MetaData
-- naming convention, ADR-0004 rule 15); UUIDv7 IDs from context.new_id or the client, no ID defaults; recorded_at on
-- every row (ADR-0007 rule 9). Every table carries company_id, FORCE ROW LEVEL SECURITY and the generated company
-- policy (ADR-0017 rule 19; ADR-0022 rule 8). References inside a company are composite on (company_id, id); composite
-- keys that carry one more column (order, warehouse, cost object, control) hold rules the ADRs state, named at the key.
-- Owner module per section in brackets (ADR-0022 rule 2): planning (layer 4), production (layer 3), inventory for the
-- demand and supply read model and the replenishment hand-over (ADR-0024 rules 8, 22).
-- Referenced tables defined elsewhere: company, item, product, partner, warehouse, bin, lot, serial_number, uom,
-- cost_center, working_calendar, variant_attribute (DS-20); product_configuration (DS-56); user_account and team
-- (DS-15); cost_object and journal tables (DS-06); document (documents, ADR-0009 rule 1, with UNIQUE (company_id, id)
-- by ADR-0052 rule 18), material_document_line and posting_period (stubs in the lab until their DDL exists).
-- Typed headers of documents (production_order, the three shop-floor documents, production_cost_settlement) share their
-- id with the document row, as DS-35 does; document state, number, document_date and partner live on that row.
-- Lines of document types use line_number as identity (ADR-0028 rule 1) and keep a surrogate id for typed references.
-- Rules that need other rows (cycles, low-level codes, validity gaps, version selection, pegging sums, tolerance,
-- backflush quantities, item both component and output) are enforced by commands and named in the ADRs; the database
-- holds what one row, a composite key or a revision trigger can hold.
-- Columns the flows need where an ADR is silent are marked "interim: not stated in ADR-00xx".
-- Not here, owned by other design items: service_receipt and purchase lines with production_order_operation_id
-- (purchasing, DS-22, ADR-0037 rules 4-5), stock_reservation and warehouse tasks (DS-42), sales_history import
-- batches (DS-21), work items for exceptions (DS-29), by_product prices (a price_list of kind by_product, DS-20).

-- ===== Company rows that serialize changes [planning, production] =====
CREATE TABLE planning_setting (                            -- one per company (ADR-0024 rule 7; ADR-0036 rules 4, 11)
    company_id                 uuid PRIMARY KEY REFERENCES company (id),
    planning_owner_id          uuid NOT NULL REFERENCES user_account (id),   -- accountable human for scheduled runs (spec 03 rule 3)
    planning_horizon_days      integer NOT NULL CONSTRAINT ck_planning_setting_horizon CHECK (planning_horizon_days > 0),
    forecast_consumption_days  integer NOT NULL DEFAULT 7 CONSTRAINT ck_planning_setting_consumption CHECK (forecast_consumption_days >= 0),   -- flagged default (rule 13)
    conversion_window_days     integer NOT NULL CONSTRAINT ck_planning_setting_conversion_window CHECK (conversion_window_days >= 0),
    backtest_weeks             integer NOT NULL CONSTRAINT ck_planning_setting_backtest CHECK (backtest_weeks > 0),
    conversion_lead_days       integer NOT NULL DEFAULT 0 CONSTRAINT ck_planning_setting_conversion_lead CHECK (conversion_lead_days >= 0),   -- working days, flagged (ADR-0036 rule 4)
    capacity_bucket            text NOT NULL DEFAULT 'week' CONSTRAINT ck_planning_setting_capacity_bucket CHECK (capacity_bucket IN ('day', 'week')),
    recorded_at                timestamptz NOT NULL
);
CREATE TABLE planning_run (                                -- RunPlanning, a long job (ADR-0024 rule 17)
    id                    uuid PRIMARY KEY,
    company_id            uuid NOT NULL REFERENCES company (id),
    planning_date         date NOT NULL,                       -- explicit business date (ADR-0007 rule 17)
    forecast_run_id       uuid,                                -- the forecast run it used (rule 11)
    requested_by_user_id  uuid NOT NULL REFERENCES user_account (id),   -- the requester, or planning_owner_id for scheduled runs
    mode                  text NOT NULL DEFAULT 'regenerative' CONSTRAINT ck_planning_run_mode CHECK (mode IN ('regenerative')),   -- Phase 1 (rule 17)
    scope_item_ids        uuid[],                              -- interim: not stated in ADR-0024 (the scope of a limited run; null = all items)
    state                 text NOT NULL DEFAULT 'running' CONSTRAINT ck_planning_run_state CHECK (state IN ('running', 'completed', 'failed')),   -- interim: not stated in ADR-0024
    output_counts         jsonb,                               -- counts per output kind (rule 17)
    input_hash            text CONSTRAINT ck_planning_run_input_hash CHECK (input_hash ~ '^[0-9a-f]{64}$'),
    output_hash           text CONSTRAINT ck_planning_run_output_hash CHECK (output_hash ~ '^[0-9a-f]{64}$'),
    started_at            timestamptz NOT NULL,                -- interim: not stated in ADR-0024 (the nightly report records run time, rule 25)
    completed_at          timestamptz,                         -- interim: not stated in ADR-0024
    recorded_at           timestamptz NOT NULL,
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, forecast_run_id) REFERENCES forecast_run (company_id, id),
    CONSTRAINT ck_planning_run_completed CHECK ((state = 'completed') = (completed_at IS NOT NULL AND input_hash IS NOT NULL AND output_hash IS NOT NULL AND output_counts IS NOT NULL))
);
CREATE TABLE planning_state (                              -- the company's planning state row; RunPlanning locks it, so a second run gets planning_run_in_progress (ADR-0024 rule 17)
    company_id             uuid PRIMARY KEY REFERENCES company (id),
    last_planning_run_id   uuid,                               -- interim: not stated in ADR-0024 (the lock row needs no column; this one names the latest completed run)
    recorded_at            timestamptz NOT NULL,
    FOREIGN KEY (company_id, last_planning_run_id) REFERENCES planning_run (company_id, id)
);
CREATE TABLE production_structure (                        -- created with the company; releases, version and setting saves lock it at class 3 (ADR-0033 rule 8; ADR-0027 rule 10)
    company_id   uuid PRIMARY KEY REFERENCES company (id),
    recorded_at  timestamptz NOT NULL
);

-- ===== Planning master data [planning] (ADR-0024 rules 1-3) =====
CREATE TABLE transfer_route (                              -- ADR-0024 rule 3; also the return route from a processor location (ADR-0037 rule 3)
    id                        uuid PRIMARY KEY,
    company_id                uuid NOT NULL REFERENCES company (id),
    source_warehouse_id       uuid NOT NULL,
    destination_warehouse_id  uuid NOT NULL,
    lead_time_days            integer NOT NULL CONSTRAINT ck_transfer_route_lead_time CHECK (lead_time_days >= 0),   -- calendar days
    is_active                 boolean NOT NULL DEFAULT true,   -- interim: not stated in ADR-0024
    recorded_at               timestamptz NOT NULL,
    -- interim: not stated in ADR-0024 (one route per warehouse pair, so "the route" of a transfer source is unambiguous)
    UNIQUE (company_id, source_warehouse_id, destination_warehouse_id),
    UNIQUE (company_id, id),
    UNIQUE (company_id, id, destination_warehouse_id),
    FOREIGN KEY (company_id, source_warehouse_id) REFERENCES warehouse (company_id, id),
    FOREIGN KEY (company_id, destination_warehouse_id) REFERENCES warehouse (company_id, id),
    CONSTRAINT ck_transfer_route_distinct CHECK (source_warehouse_id <> destination_warehouse_id)
);
-- Cycles of transfer sources are rejected by the command (planning_network_cycle, rule 3).
CREATE TABLE item_warehouse_planning (                     -- an item without a row in a warehouse is not planned there (ADR-0024 rule 1)
    id                      uuid PRIMARY KEY,
    company_id              uuid NOT NULL,
    item_id                 uuid NOT NULL,
    warehouse_id            uuid NOT NULL,
    planning_method         text NOT NULL CONSTRAINT ck_item_warehouse_planning_method CHECK (planning_method IN ('reorder_point', 'min_max', 'net_requirements')),
    replenishment_source    text NOT NULL CONSTRAINT ck_item_warehouse_planning_source CHECK (replenishment_source IN ('purchase', 'transfer', 'production')),   -- production: ADR-0033 rule 14
    transfer_route_id       uuid,                               -- "a transfer replenishment source names a route" (rule 3)
    reorder_point           types.quantity,
    minimum_quantity        types.quantity,
    maximum_quantity        types.quantity,
    safety_stock_method     text NOT NULL DEFAULT 'fixed' CONSTRAINT ck_item_warehouse_planning_safety_method CHECK (safety_stock_method IN ('fixed', 'service_level')),
    safety_stock_quantity   types.quantity NOT NULL DEFAULT 0 CONSTRAINT ck_item_warehouse_planning_safety_stock CHECK (safety_stock_quantity >= 0),
    service_level_percent   types.percent,
    lot_size_method         text NOT NULL DEFAULT 'exact' CONSTRAINT ck_item_warehouse_planning_lot_size CHECK (lot_size_method IN ('exact', 'fixed', 'supply_period')),
    fixed_lot_quantity      types.quantity,
    supply_period_days      integer,
    firm_horizon_days       integer NOT NULL DEFAULT 0 CONSTRAINT ck_item_warehouse_planning_firm_horizon CHECK (firm_horizon_days >= 0),   -- default 0: no fence (rule 19)
    receiving_days          integer NOT NULL DEFAULT 0 CONSTRAINT ck_item_warehouse_planning_receiving CHECK (receiving_days >= 0),
    planning_strategy       text NOT NULL DEFAULT 'make_to_stock' CONSTRAINT ck_item_warehouse_planning_strategy CHECK (planning_strategy IN ('make_to_stock', 'make_to_order')),
    recorded_at             timestamptz NOT NULL,
    UNIQUE (company_id, item_id, warehouse_id),
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, item_id) REFERENCES item (company_id, id),
    FOREIGN KEY (company_id, warehouse_id) REFERENCES warehouse (company_id, id),
    -- the route ends in this row's warehouse
    CONSTRAINT fk_item_warehouse_planning_route FOREIGN KEY (company_id, transfer_route_id, warehouse_id) REFERENCES transfer_route (company_id, id, destination_warehouse_id),
    CONSTRAINT ck_item_warehouse_planning_route CHECK ((replenishment_source = 'transfer') = (transfer_route_id IS NOT NULL)),
    CONSTRAINT ck_item_warehouse_planning_reorder_point CHECK (planning_method <> 'reorder_point' OR coalesce(reorder_point >= 0, false)),
    CONSTRAINT ck_item_warehouse_planning_min_max CHECK (planning_method <> 'min_max' OR coalesce(minimum_quantity >= 0 AND maximum_quantity >= minimum_quantity, false)),
    CONSTRAINT ck_item_warehouse_planning_service_level CHECK ((safety_stock_method = 'service_level') = (service_level_percent IS NOT NULL)
                                                                AND (service_level_percent IS NULL OR (service_level_percent > 0 AND service_level_percent < 100))),
    CONSTRAINT ck_item_warehouse_planning_fixed_lot CHECK ((lot_size_method = 'fixed') = (fixed_lot_quantity IS NOT NULL) AND coalesce(fixed_lot_quantity, 1) > 0),
    CONSTRAINT ck_item_warehouse_planning_supply_period CHECK ((lot_size_method = 'supply_period') = (supply_period_days IS NOT NULL) AND coalesce(supply_period_days, 1) > 0),
    -- make_to_order only with source production, method net_requirements and lot size exact (make_to_order_not_allowed, ADR-0036 rule 9)
    CONSTRAINT ck_item_warehouse_planning_make_to_order CHECK (planning_strategy = 'make_to_stock'
        OR (replenishment_source = 'production' AND planning_method = 'net_requirements' AND lot_size_method = 'exact'))
);
CREATE TABLE supplier_item (                               -- the only home of supplier minimums, multiples and preference (ADR-0024 rule 2)
    id                        uuid PRIMARY KEY,
    company_id                uuid NOT NULL,
    supplier_partner_id       uuid NOT NULL,
    item_id                   uuid NOT NULL,                  -- also a service item of an external operation (ADR-0037 rule 3)
    order_uom_id              uuid NOT NULL REFERENCES uom (id),   -- the supplier's order unit: the inventory unit or an active product unit (ADR-0056 rule 14)
    partner_item_id           uuid REFERENCES partner_item (id),   -- the supplier's own code (ADR-0019 rule 6)
    supplier_processing_days  integer NOT NULL CONSTRAINT ck_supplier_item_processing CHECK (supplier_processing_days >= 0),   -- on the supplier's calendar
    transit_days              integer NOT NULL CONSTRAINT ck_supplier_item_transit CHECK (transit_days >= 0),                 -- calendar days
    minimum_order_quantity    types.quantity NOT NULL DEFAULT 0 CONSTRAINT ck_supplier_item_minimum CHECK (minimum_order_quantity >= 0),   -- in order_uom_id
    order_multiple            types.quantity CONSTRAINT ck_supplier_item_multiple CHECK (order_multiple > 0),                 -- in order_uom_id; null = none
    is_preferred              boolean NOT NULL DEFAULT false,  -- none or several valid preferred rows give planning_parameter_missing (a run check, not a key)
    start_date                date NOT NULL,
    end_date                  date,                            -- inclusive; null = open
    recorded_at               timestamptz NOT NULL,
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, supplier_partner_id) REFERENCES partner (company_id, id),
    FOREIGN KEY (company_id, item_id) REFERENCES item (company_id, id),
    CONSTRAINT ck_supplier_item_dates CHECK (end_date IS NULL OR end_date >= start_date),
    -- keyed by (company, supplier partner, item): one row valid on any date
    CONSTRAINT ex_supplier_item_overlap EXCLUDE USING gist (
        company_id WITH =, supplier_partner_id WITH =, item_id WITH =, daterange(start_date, end_date, '[]') WITH &&)
);
CREATE TABLE supplier_purchasing_term (                    -- one row per supplier partner (ADR-0024 rule 2)
    company_id             uuid NOT NULL,
    supplier_partner_id    uuid NOT NULL,
    minimum_order_amount   types.amount CONSTRAINT ck_supplier_purchasing_term_minimum CHECK (minimum_order_amount >= 0),
    currency               text REFERENCES currency (code),
    container_volume       types.quantity CONSTRAINT ck_supplier_purchasing_term_volume CHECK (container_volume > 0),
    volume_uom_id          uuid REFERENCES uom (id),        -- interim: not stated in ADR-0024 (the unit of container_volume)
    container_weight       types.quantity CONSTRAINT ck_supplier_purchasing_term_weight CHECK (container_weight > 0),
    weight_uom_id          uuid REFERENCES uom (id),        -- interim: not stated in ADR-0024 (the unit of container_weight)
    order_cycle_days       integer CONSTRAINT ck_supplier_purchasing_term_cycle CHECK (order_cycle_days > 0),
    recorded_at            timestamptz NOT NULL,
    PRIMARY KEY (company_id, supplier_partner_id),
    FOREIGN KEY (company_id, supplier_partner_id) REFERENCES partner (company_id, id),
    CONSTRAINT ck_supplier_purchasing_term_currency CHECK ((minimum_order_amount IS NULL) = (currency IS NULL)),
    CONSTRAINT ck_supplier_purchasing_term_volume_uom CHECK ((container_volume IS NULL) = (volume_uom_id IS NULL)),
    CONSTRAINT ck_supplier_purchasing_term_weight_uom CHECK ((container_weight IS NULL) = (weight_uom_id IS NULL))
);
CREATE TABLE supplier_item_lead_time (                     -- measured, refreshed by the forecast job, never applied without approval (ADR-0024 rule 2)
    company_id                uuid NOT NULL,
    supplier_partner_id       uuid NOT NULL,
    item_id                   uuid NOT NULL,
    mean_days                 numeric(12,4) NOT NULL CONSTRAINT ck_supplier_item_lead_time_mean CHECK (mean_days >= 0),
    standard_deviation_days   numeric(12,4) NOT NULL CONSTRAINT ck_supplier_item_lead_time_deviation CHECK (standard_deviation_days >= 0),
    sample_count              integer NOT NULL CONSTRAINT ck_supplier_item_lead_time_samples CHECK (sample_count > 0),   -- interim: not stated in ADR-0024
    forecast_run_id           uuid,                            -- interim: not stated in ADR-0024 (the refreshing run)
    recorded_at               timestamptz NOT NULL,
    PRIMARY KEY (company_id, supplier_partner_id, item_id),
    FOREIGN KEY (company_id, supplier_partner_id) REFERENCES partner (company_id, id),
    FOREIGN KEY (company_id, item_id) REFERENCES item (company_id, id),
    FOREIGN KEY (company_id, forecast_run_id) REFERENCES forecast_run (company_id, id)
);

-- ===== Demand history and forecast [planning] (ADR-0024 rules 10-13) =====
CREATE TABLE sales_history (                               -- weeks before the first posting, written by ImportSalesHistory (rule 10)
    company_id    uuid NOT NULL,
    item_id       uuid NOT NULL,
    warehouse_id  uuid NOT NULL,
    iso_week      text NOT NULL CONSTRAINT ck_sales_history_iso_week CHECK (iso_week ~ '^[0-9]{4}-W(0[1-9]|[1-4][0-9]|5[0-3])$'),
    quantity      types.quantity NOT NULL,                     -- inventory unit; issues minus returns may be negative
    recorded_at   timestamptz NOT NULL,
    PRIMARY KEY (company_id, item_id, warehouse_id, iso_week),
    FOREIGN KEY (company_id, item_id) REFERENCES item (company_id, id),
    FOREIGN KEY (company_id, warehouse_id) REFERENCES warehouse (company_id, id)
);
CREATE TABLE demand_event (                                -- e.g. tet; company data (rule 10)
    id           uuid PRIMARY KEY,
    company_id   uuid NOT NULL REFERENCES company (id),
    code         text NOT NULL,
    name         text NOT NULL,
    recorded_at  timestamptz NOT NULL,
    UNIQUE (company_id, code),
    UNIQUE (company_id, id)
);
CREATE TABLE demand_event_window (                         -- the event's window of dates per year, so a moving holiday stays aligned
    company_id       uuid NOT NULL,
    demand_event_id  uuid NOT NULL,
    start_date       date NOT NULL,
    end_date         date NOT NULL,
    recorded_at      timestamptz NOT NULL,
    PRIMARY KEY (demand_event_id, start_date),
    FOREIGN KEY (company_id, demand_event_id) REFERENCES demand_event (company_id, id),
    CONSTRAINT ck_demand_event_window_dates CHECK (end_date >= start_date),
    CONSTRAINT ex_demand_event_window_overlap EXCLUDE USING gist (demand_event_id WITH =, daterange(start_date, end_date, '[]') WITH &&)
);
CREATE TABLE forecast_run (                                -- RunForecast, a long job (rules 11, 17); table named by the holistic review (ADR-0024 rule 21 note)
    id                    uuid PRIMARY KEY,
    company_id            uuid NOT NULL REFERENCES company (id),
    planning_date         date NOT NULL,
    method                text NOT NULL DEFAULT 'moving_average' CONSTRAINT ck_forecast_run_method CHECK (method IN ('moving_average', 'by_backtest')),   -- by_backtest: the later slice
    requested_by_user_id  uuid NOT NULL REFERENCES user_account (id),
    check_results         jsonb NOT NULL DEFAULT '[]',          -- e.g. forecast_history_insufficient per (item, warehouse); not hashed (rule 17)
    input_hash            text CONSTRAINT ck_forecast_run_input_hash CHECK (input_hash ~ '^[0-9a-f]{64}$'),
    output_hash           text CONSTRAINT ck_forecast_run_output_hash CHECK (output_hash ~ '^[0-9a-f]{64}$'),
    recorded_at           timestamptz NOT NULL,
    UNIQUE (company_id, id)
);
CREATE TABLE forecast_line (                               -- statistical forecast per day after the weekday spread; never overwritten by adjustments (rules 10-12)
    company_id       uuid NOT NULL,
    forecast_run_id  uuid NOT NULL,
    item_id          uuid NOT NULL,
    warehouse_id     uuid NOT NULL,
    forecast_date    date NOT NULL,
    quantity         types.quantity NOT NULL CONSTRAINT ck_forecast_line_quantity CHECK (quantity >= 0),   -- inventory unit, remainder carried forward (rule 10)
    -- the forecast tier of holistic decision F0 (ADR-0024 rule 11 notes): short_mean (1-7 weeks), unindexed (8-51 weeks:
    -- 8-week average), indexed (52 weeks or more); with no history the run writes no line, and the check result
    -- forecast_history_insufficient carries details.tier none
    forecast_tier    text NOT NULL CONSTRAINT ck_forecast_line_tier CHECK (forecast_tier IN ('short_mean', 'unindexed', 'indexed')),
    index_factor     numeric(12,6) NOT NULL DEFAULT 1 CONSTRAINT ck_forecast_line_index_factor CHECK (index_factor >= 0),   -- interim: not stated in ADR-0024 (seasonal or event index applied)
    demand_event_id  uuid,                                     -- interim: not stated in ADR-0024 (the event whose index replaced the seasonal one)
    recorded_at      timestamptz NOT NULL,
    PRIMARY KEY (forecast_run_id, item_id, warehouse_id, forecast_date),
    FOREIGN KEY (company_id, forecast_run_id) REFERENCES forecast_run (company_id, id),
    FOREIGN KEY (company_id, item_id) REFERENCES item (company_id, id),
    FOREIGN KEY (company_id, warehouse_id) REFERENCES warehouse (company_id, id),
    FOREIGN KEY (company_id, demand_event_id) REFERENCES demand_event (company_id, id),
    CONSTRAINT ck_forecast_line_index CHECK (forecast_tier = 'indexed' OR (index_factor = 1 AND demand_event_id IS NULL))
);
CREATE TABLE forecast_adjustment (                         -- CreateForecastAdjustment, CancelForecastAdjustment; agent proposals are change proposals (rule 12)
    id                   uuid PRIMARY KEY,
    company_id           uuid NOT NULL,
    item_id              uuid NOT NULL,
    warehouse_id         uuid NOT NULL,
    start_date           date NOT NULL,
    end_date             date NOT NULL,
    quantity             types.quantity,                       -- added per day of the range, inventory unit
    factor               numeric(12,6) CONSTRAINT ck_forecast_adjustment_factor CHECK (factor >= 0),
    created_by_user_id   uuid NOT NULL REFERENCES user_account (id),   -- the author (a human; approval is human)
    reason               text NOT NULL,
    change_proposal_id   uuid,                                 -- interim: not stated in ADR-0024 (the approved proposal, when an agent drafted it; no DDL yet)
    canceled_at          timestamptz,                          -- set by CancelForecastAdjustment; rows are never overwritten
    recorded_at          timestamptz NOT NULL,
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, item_id) REFERENCES item (company_id, id),
    FOREIGN KEY (company_id, warehouse_id) REFERENCES warehouse (company_id, id),
    CONSTRAINT ck_forecast_adjustment_dates CHECK (end_date >= start_date),
    CONSTRAINT ck_forecast_adjustment_one CHECK ((quantity IS NULL) <> (factor IS NULL))
);

-- ===== Demand and supply read model [inventory] (ADR-0024 rule 8; ADR-0028 rule 2) =====
-- A table, not a view: rows are never deleted or rebuilt, unique per source line and direction, closed with
-- closed_reason, and referred to by execution tables (stock_reservation, warehouse_task, planned_order_pegging). Documents write it
-- through posting interfaces in their own transactions. The step-5 line tables have no DDL yet, so their columns carry
-- no key; the keys are added at step 5 (ADR-0028 rule 2). The production columns, for_demand_supply_line_id and
-- owner_partner_id are the B3 columns: the author's (ADR-0028 rule 2), present here as the holistic review's interim.
CREATE TABLE demand_supply_line (
    id                              uuid PRIMARY KEY,
    company_id                      uuid NOT NULL,
    item_id                         uuid NOT NULL,
    warehouse_id                    uuid NOT NULL,
    direction                       text NOT NULL CONSTRAINT ck_demand_supply_line_direction CHECK (direction IN ('demand', 'supply')),
    open_quantity                   types.quantity NOT NULL CONSTRAINT ck_demand_supply_line_open_quantity CHECK (open_quantity >= 0),   -- inventory unit; never below 0 (ADR-0034 rule 9)
    requested_date                  date NOT NULL,
    ordered_date                    date,                       -- supply: start of the measured lead time (ADR-0024 rule 2)
    source_kind                     text NOT NULL CONSTRAINT ck_demand_supply_line_source_kind CHECK (source_kind IN (
                                        'sales_order_line', 'purchase_order_line', 'purchase_request_line', 'transfer_order_line',
                                        'production_order_component', 'production_order_output')),
    sales_order_line_id             uuid,                       -- key added at step 5
    purchase_order_line_id          uuid,                       -- key added at step 5
    purchase_request_line_id        uuid,                       -- key added at step 5
    transfer_order_line_id          uuid,                       -- key added with transfer orders (step 3)
    production_order_component_id   uuid,                       -- B3, interim (ADR-0034 rule 9)
    production_order_output_id      uuid,                       -- B3, interim (ADR-0034 rule 9)
    for_demand_supply_line_id       uuid,                       -- B3, interim: make-to-order supply link (ADR-0036 rule 9)
    owner_partner_id                uuid,                       -- B3, interim: reserved owner axis, null for own stock (ADR-0037 rule 7)
    origin_planned_order_id         uuid,                       -- ADR-0024 rule 8; INV-62
    closed_reason                   text CONSTRAINT ck_demand_supply_line_closed_reason CHECK (closed_reason IN ('fulfilled', 'canceled')),
    -- commercial holistic fix (ADR-0047 note): released when empty. Unreleased demand rows are not demand; purchase supply
    -- rows count for planning while held, but goods are received only once released. Production component and output
    -- rows carry not_approved until their order is approved (released), like sales and purchase rows (ADR-0024 rule 8 note).
    hold_reasons                    text[] NOT NULL DEFAULT '{}' CONSTRAINT ck_demand_supply_line_hold_reasons
                                        CHECK (hold_reasons <@ ARRAY['not_approved', 'credit_hold']::text[]),
    recorded_at                     timestamptz NOT NULL,
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, item_id) REFERENCES item (company_id, id),
    FOREIGN KEY (company_id, warehouse_id) REFERENCES warehouse (company_id, id),
    FOREIGN KEY (company_id, owner_partner_id) REFERENCES partner (company_id, id),
    FOREIGN KEY (company_id, for_demand_supply_line_id) REFERENCES demand_supply_line (company_id, id),
    -- exactly the source column its kind names
    CONSTRAINT ck_demand_supply_line_source CHECK (num_nonnulls(sales_order_line_id, purchase_order_line_id, purchase_request_line_id,
                                                               transfer_order_line_id, production_order_component_id, production_order_output_id) = 1
        AND (source_kind = 'sales_order_line') = (sales_order_line_id IS NOT NULL)
        AND (source_kind = 'purchase_order_line') = (purchase_order_line_id IS NOT NULL)
        AND (source_kind = 'purchase_request_line') = (purchase_request_line_id IS NOT NULL)
        AND (source_kind = 'transfer_order_line') = (transfer_order_line_id IS NOT NULL)
        AND (source_kind = 'production_order_component') = (production_order_component_id IS NOT NULL)
        AND (source_kind = 'production_order_output') = (production_order_output_id IS NOT NULL)),
    -- the direction each kind counts as (rule 8; ADR-0034 rule 9); a transfer line is demand at the source and supply at the destination
    CONSTRAINT ck_demand_supply_line_kind_direction CHECK (
        CASE source_kind WHEN 'sales_order_line' THEN direction = 'demand' WHEN 'production_order_component' THEN direction = 'demand'
                         WHEN 'transfer_order_line' THEN true ELSE direction = 'supply' END),
    CONSTRAINT ck_demand_supply_line_ordered_date CHECK (ordered_date IS NULL OR direction = 'supply'),
    CONSTRAINT ck_demand_supply_line_for_demand CHECK (for_demand_supply_line_id IS NULL OR source_kind = 'production_order_output'),
    CONSTRAINT ck_demand_supply_line_not_self CHECK (for_demand_supply_line_id IS DISTINCT FROM id)
);
CREATE UNIQUE INDEX ux_demand_supply_line_sales_order_line ON demand_supply_line (sales_order_line_id, direction) WHERE sales_order_line_id IS NOT NULL;
CREATE UNIQUE INDEX ux_demand_supply_line_purchase_order_line ON demand_supply_line (purchase_order_line_id, direction) WHERE purchase_order_line_id IS NOT NULL;
CREATE UNIQUE INDEX ux_demand_supply_line_purchase_request_line ON demand_supply_line (purchase_request_line_id, direction) WHERE purchase_request_line_id IS NOT NULL;
CREATE UNIQUE INDEX ux_demand_supply_line_transfer_order_line ON demand_supply_line (transfer_order_line_id, direction) WHERE transfer_order_line_id IS NOT NULL;
CREATE UNIQUE INDEX ux_demand_supply_line_component ON demand_supply_line (production_order_component_id, direction) WHERE production_order_component_id IS NOT NULL;
CREATE UNIQUE INDEX ux_demand_supply_line_output ON demand_supply_line (production_order_output_id, direction) WHERE production_order_output_id IS NOT NULL;
CREATE INDEX ix_demand_supply_line_open ON demand_supply_line (company_id, item_id, warehouse_id, requested_date) WHERE closed_reason IS NULL;
CREATE INDEX ix_demand_supply_line_held ON demand_supply_line (company_id) WHERE cardinality(hold_reasons) > 0;
CREATE INDEX ix_demand_supply_line_origin_planned_order_id ON demand_supply_line (origin_planned_order_id) WHERE origin_planned_order_id IS NOT NULL;

-- ===== Production master data [production] (ADR-0033) =====
CREATE TABLE activity_type (                               -- e.g. setup, machine, labor (ADR-0033 rule 12)
    id           uuid PRIMARY KEY,
    company_id   uuid NOT NULL REFERENCES company (id),
    code         text NOT NULL,
    name         text NOT NULL,
    time_uom_id  uuid NOT NULL REFERENCES uom (id),            -- a unit of kind time (command check)
    is_active    boolean NOT NULL DEFAULT true,
    recorded_at  timestamptz NOT NULL,
    UNIQUE (company_id, code),
    UNIQUE (company_id, id)
);
CREATE TABLE work_center (                                 -- ADR-0033 rule 11
    id                       uuid PRIMARY KEY,
    company_id               uuid NOT NULL,
    code                     text NOT NULL,
    name                     text NOT NULL,
    production_warehouse_id  uuid NOT NULL,                     -- a physical warehouse (command check)
    working_calendar_id      uuid NOT NULL,
    capacity_units           integer NOT NULL DEFAULT 1 CONSTRAINT ck_work_center_capacity_units CHECK (capacity_units > 0),
    hours_per_day            numeric(6,2) NOT NULL CONSTRAINT ck_work_center_hours_per_day CHECK (hours_per_day > 0 AND hours_per_day <= 24),
    efficiency_percent       types.percent NOT NULL DEFAULT 100 CONSTRAINT ck_work_center_efficiency CHECK (efficiency_percent > 0),
    is_capacity_relevant     boolean NOT NULL DEFAULT true,
    cost_center_id           uuid NOT NULL,                     -- where its overhead is collected (DS-53)
    supply_bin_id            uuid,                              -- bin type production (command check; ADR-0034 rule 10)
    output_bin_id            uuid,
    is_active                boolean NOT NULL DEFAULT true,
    recorded_at              timestamptz NOT NULL,
    UNIQUE (company_id, code),
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, production_warehouse_id) REFERENCES warehouse (company_id, id),
    FOREIGN KEY (company_id, working_calendar_id) REFERENCES working_calendar (company_id, id),
    FOREIGN KEY (company_id, cost_center_id) REFERENCES cost_center (company_id, id),
    -- the bins lie in the work center's warehouse
    CONSTRAINT fk_work_center_supply_bin FOREIGN KEY (supply_bin_id, production_warehouse_id) REFERENCES bin (id, warehouse_id),
    CONSTRAINT fk_work_center_output_bin FOREIGN KEY (output_bin_id, production_warehouse_id) REFERENCES bin (id, warehouse_id)
);
CREATE TABLE work_center_activity (                        -- activity types a work center records, with defaults copied into new operations
    company_id        uuid NOT NULL,
    work_center_id    uuid NOT NULL,
    activity_type_id  uuid NOT NULL,
    quantity          types.quantity NOT NULL CONSTRAINT ck_work_center_activity_quantity CHECK (quantity >= 0),
    basis             text NOT NULL CONSTRAINT ck_work_center_activity_basis CHECK (basis IN ('per_order', 'per_base_quantity')),
    recorded_at       timestamptz NOT NULL,
    PRIMARY KEY (work_center_id, activity_type_id),
    FOREIGN KEY (company_id, work_center_id) REFERENCES work_center (company_id, id),
    FOREIGN KEY (company_id, activity_type_id) REFERENCES activity_type (company_id, id)
);
CREATE TABLE bill_of_materials (                           -- ADR-0033 rule 3; product_id for a configurable product (ADR-0046 rule 12)
    id           uuid PRIMARY KEY,
    company_id   uuid NOT NULL,
    item_id      uuid,                                         -- the main output
    product_id   uuid,
    usage        text NOT NULL DEFAULT 'production' CONSTRAINT ck_bill_of_materials_usage CHECK (usage IN ('production', 'kit')),   -- kit: rules in DS-22
    alternative  text NOT NULL,
    name         text NOT NULL,
    is_active    boolean NOT NULL DEFAULT true,
    recorded_at  timestamptz NOT NULL,
    UNIQUE NULLS NOT DISTINCT (company_id, item_id, product_id, usage, alternative),
    UNIQUE (company_id, id),
    UNIQUE (company_id, id, usage),
    FOREIGN KEY (company_id, item_id) REFERENCES item (company_id, id),
    FOREIGN KEY (company_id, product_id) REFERENCES product (company_id, id),
    CONSTRAINT ck_bill_of_materials_output CHECK ((item_id IS NULL) <> (product_id IS NULL))
);
CREATE TABLE bill_of_materials_revision (                  -- immutable once released (ADR-0033 rules 3-4)
    id                             uuid PRIMARY KEY,
    company_id                     uuid NOT NULL,
    bill_of_materials_id           uuid NOT NULL,
    revision                       integer NOT NULL CONSTRAINT ck_bill_of_materials_revision_revision CHECK (revision > 0),
    state                          text NOT NULL DEFAULT 'draft' CONSTRAINT ck_bill_of_materials_revision_state CHECK (state IN ('draft', 'released')),
    start_date                     date NOT NULL,
    base_quantity                  types.quantity NOT NULL CONSTRAINT ck_bill_of_materials_revision_base CHECK (base_quantity > 0),   -- main output's inventory unit
    assembly_scrap_percent         types.percent NOT NULL DEFAULT 0 CONSTRAINT ck_bill_of_materials_revision_scrap CHECK (assembly_scrap_percent >= 0 AND assembly_scrap_percent < 100),
    main_output_cost_coefficient   numeric(18,6) NOT NULL DEFAULT 1 CONSTRAINT ck_bill_of_materials_revision_coefficient CHECK (main_output_cost_coefficient >= 0),
    content_hash                   text CONSTRAINT ck_bill_of_materials_revision_hash CHECK (content_hash ~ '^[0-9a-f]{64}$'),
    released_at                    timestamptz,
    copy_from_revision_id          uuid,
    recorded_at                    timestamptz NOT NULL,
    UNIQUE (bill_of_materials_id, revision),
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, bill_of_materials_id) REFERENCES bill_of_materials (company_id, id),
    FOREIGN KEY (company_id, copy_from_revision_id) REFERENCES bill_of_materials_revision (company_id, id),
    CONSTRAINT ck_bill_of_materials_revision_released CHECK ((state = 'released') = (content_hash IS NOT NULL AND released_at IS NOT NULL))
);
-- At most one draft per bill of materials (draft_revision_exists, ADR-0033 rule 3).
CREATE UNIQUE INDEX ux_bill_of_materials_revision_draft ON bill_of_materials_revision (bill_of_materials_id) WHERE state = 'draft';
CREATE TABLE bill_of_materials_component (                 -- ADR-0033 rule 6; selection and sizing: ADR-0046 rule 12
    id                              uuid PRIMARY KEY,
    company_id                      uuid NOT NULL,
    bill_of_materials_revision_id   uuid NOT NULL,
    position                        integer NOT NULL CONSTRAINT ck_bill_of_materials_component_position CHECK (position > 0),
    component_item_id               uuid NOT NULL,              -- an active item of a stock product (checked at release)
    quantity                        types.quantity NOT NULL,    -- per base quantity, in uom_id
    uom_id                          uuid NOT NULL REFERENCES uom (id),
    -- the conversion snapshot, no default factor: the exact quantity in the component's inventory unit is
    -- quantity * uom_numerator / uom_denominator, never stored, rounded once per order line (ADR-0033 rule 6; ADR-0056 rules 9, 17)
    uom_numerator                   bigint NOT NULL,
    uom_denominator                 bigint NOT NULL,
    uom_factor_source               text NOT NULL,
    issue_multiple                  types.quantity CONSTRAINT ck_bill_of_materials_component_issue_multiple CHECK (issue_multiple > 0),   -- in uom_id: requirements round up to whole multiples
    component_scrap_percent         types.percent NOT NULL DEFAULT 0 CONSTRAINT ck_bill_of_materials_component_scrap CHECK (component_scrap_percent >= 0 AND component_scrap_percent < 100),
    is_fixed_quantity               boolean NOT NULL DEFAULT false,
    operation_number                integer CONSTRAINT ck_bill_of_materials_component_operation CHECK (operation_number > 0),   -- must exist in the paired routing (operation_not_in_routing, release check)
    consumption_method              text NOT NULL DEFAULT 'manual' CONSTRAINT ck_bill_of_materials_component_consumption CHECK (consumption_method IN ('manual', 'backflush_at_operation', 'backflush_at_receipt')),
    selection_condition             jsonb NOT NULL DEFAULT '{}',   -- product-level bills only (ADR-0046 rule 12); empty = always
    sizing                          text NOT NULL DEFAULT 'fixed' CONSTRAINT ck_bill_of_materials_component_sizing CHECK (sizing IN ('fixed', 'linear')),
    quantity_per_value              types.quantity,             -- linear: quantity + quantity_per_value * value
    sizing_attribute_id             uuid,                       -- interim: not stated in ADR-0046 (the numeric item-defining characteristic of linear sizing)
    sizing_value_type               text NOT NULL DEFAULT 'number' CONSTRAINT ck_bill_of_materials_component_sizing_type CHECK (sizing_value_type = 'number'),
    recorded_at                     timestamptz NOT NULL,
    UNIQUE (bill_of_materials_revision_id, position),
    FOREIGN KEY (company_id, bill_of_materials_revision_id) REFERENCES bill_of_materials_revision (company_id, id),
    FOREIGN KEY (company_id, component_item_id) REFERENCES item (company_id, id),
    CONSTRAINT fk_bill_of_materials_component_sizing FOREIGN KEY (company_id, sizing_attribute_id, sizing_value_type) REFERENCES variant_attribute (company_id, id, value_type),
    -- fixed sizing needs a positive quantity; a linear base may be zero or negative (e.g. -0.4 + 0.001 * width): the
    -- result at the characteristic's minimum and maximum is a release check (configured_quantity_negative, ADR-0046
    -- rule 12 and its note), and a zero result drops the line
    CONSTRAINT ck_bill_of_materials_component_quantity CHECK (quantity > 0 OR sizing = 'linear'),
    CONSTRAINT ck_bill_of_materials_component_linear CHECK ((sizing = 'linear') = (quantity_per_value IS NOT NULL AND sizing_attribute_id IS NOT NULL)),
    CONSTRAINT ck_bill_of_materials_component_uom_factor CHECK (uom_numerator > 0 AND uom_denominator > 0 AND uom_factor_source IN ('identity', 'item', 'product', 'global')
        AND (uom_factor_source <> 'identity' OR (uom_numerator = 1 AND uom_denominator = 1)))
);
CREATE TABLE bill_of_materials_output (                    -- co-products and by-products besides the main output (ADR-0033 rule 7)
    id                              uuid PRIMARY KEY,
    company_id                      uuid NOT NULL,
    bill_of_materials_revision_id   uuid NOT NULL,
    position                        integer NOT NULL CONSTRAINT ck_bill_of_materials_output_position CHECK (position > 0),
    output_item_id                  uuid NOT NULL,
    quantity                        types.quantity NOT NULL CONSTRAINT ck_bill_of_materials_output_quantity CHECK (quantity > 0),
    uom_id                          uuid NOT NULL REFERENCES uom (id),
    uom_numerator                   bigint NOT NULL,            -- the conversion snapshot, as components (ADR-0056 rule 17)
    uom_denominator                 bigint NOT NULL,
    uom_factor_source               text NOT NULL,
    output_type                     text NOT NULL CONSTRAINT ck_bill_of_materials_output_type CHECK (output_type IN ('co_product', 'by_product')),
    cost_coefficient                numeric(18,6),              -- co-products; data only (rule 7)
    recorded_at                     timestamptz NOT NULL,
    UNIQUE (bill_of_materials_revision_id, position),
    FOREIGN KEY (company_id, bill_of_materials_revision_id) REFERENCES bill_of_materials_revision (company_id, id),
    FOREIGN KEY (company_id, output_item_id) REFERENCES item (company_id, id),
    CONSTRAINT ck_bill_of_materials_output_coefficient CHECK ((output_type = 'co_product') = (cost_coefficient IS NOT NULL) AND coalesce(cost_coefficient, 0) >= 0),
    CONSTRAINT ck_bill_of_materials_output_uom_factor CHECK (uom_numerator > 0 AND uom_denominator > 0 AND uom_factor_source IN ('identity', 'item', 'product', 'global')
        AND (uom_factor_source <> 'identity' OR (uom_numerator = 1 AND uom_denominator = 1)))
);
CREATE TABLE routing (                                     -- may serve several items; with conditions, one configurable product (ADR-0033 rule 9; ADR-0046 rule 12)
    id           uuid PRIMARY KEY,
    company_id   uuid NOT NULL REFERENCES company (id),
    code         text NOT NULL,
    name         text NOT NULL,
    is_active    boolean NOT NULL DEFAULT true,
    recorded_at  timestamptz NOT NULL,
    UNIQUE (company_id, code),
    UNIQUE (company_id, id)
);
CREATE TABLE routing_revision (                            -- rules 3 and 4 apply as to bill of materials revisions
    id                     uuid PRIMARY KEY,
    company_id             uuid NOT NULL,
    routing_id             uuid NOT NULL,
    revision               integer NOT NULL CONSTRAINT ck_routing_revision_revision CHECK (revision > 0),
    state                  text NOT NULL DEFAULT 'draft' CONSTRAINT ck_routing_revision_state CHECK (state IN ('draft', 'released')),
    start_date             date NOT NULL,
    base_quantity          types.quantity NOT NULL CONSTRAINT ck_routing_revision_base CHECK (base_quantity > 0),
    content_hash           text CONSTRAINT ck_routing_revision_hash CHECK (content_hash ~ '^[0-9a-f]{64}$'),
    released_at            timestamptz,
    copy_from_revision_id  uuid,
    recorded_at            timestamptz NOT NULL,
    UNIQUE (routing_id, revision),
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, routing_id) REFERENCES routing (company_id, id),
    FOREIGN KEY (company_id, copy_from_revision_id) REFERENCES routing_revision (company_id, id),
    CONSTRAINT ck_routing_revision_released CHECK ((state = 'released') = (content_hash IS NOT NULL AND released_at IS NOT NULL))
);
CREATE UNIQUE INDEX ux_routing_revision_draft ON routing_revision (routing_id) WHERE state = 'draft';
CREATE TABLE routing_operation (                           -- one linear sequence (ADR-0033 rule 10); external operations: ADR-0037 rule 2
    id                        uuid PRIMARY KEY,
    company_id                uuid NOT NULL,
    routing_revision_id       uuid NOT NULL,
    operation_number          integer NOT NULL CONSTRAINT ck_routing_operation_number CHECK (operation_number > 0),
    work_center_id            uuid,                            -- required for internal, optional for external
    description               text,
    control                   text NOT NULL DEFAULT 'internal' CONSTRAINT ck_routing_operation_control CHECK (control IN ('internal', 'external')),
    service_item_id           uuid,                            -- external: an item of a service product
    default_supplier_id       uuid,                            -- external: the purchase may choose another supplier
    is_milestone              boolean NOT NULL DEFAULT false,
    setup_duration            numeric(12,4) NOT NULL DEFAULT 0 CONSTRAINT ck_routing_operation_setup CHECK (setup_duration >= 0),   -- hours per order
    run_duration              numeric(12,4) NOT NULL DEFAULT 0 CONSTRAINT ck_routing_operation_run CHECK (run_duration >= 0),       -- hours per base quantity
    operation_scrap_percent   types.percent NOT NULL DEFAULT 0 CONSTRAINT ck_routing_operation_scrap CHECK (operation_scrap_percent >= 0 AND operation_scrap_percent < 100),
    queue_time                numeric(12,4) NOT NULL DEFAULT 0 CONSTRAINT ck_routing_operation_queue CHECK (queue_time >= 0),      -- hours
    move_time                 numeric(12,4) NOT NULL DEFAULT 0 CONSTRAINT ck_routing_operation_move CHECK (move_time >= 0),        -- hours
    selection_condition       jsonb NOT NULL DEFAULT '{}',      -- ADR-0046 rule 12
    -- linear sizing of durations (ADR-0046 rule 12); interim: not stated in ADR-0046 (column names)
    setup_duration_per_value  numeric(12,4),
    run_duration_per_value    numeric(12,4),
    sizing_attribute_id       uuid,
    sizing_value_type         text NOT NULL DEFAULT 'number' CONSTRAINT ck_routing_operation_sizing_type CHECK (sizing_value_type = 'number'),
    recorded_at               timestamptz NOT NULL,
    UNIQUE (routing_revision_id, operation_number),
    UNIQUE (company_id, id),
    UNIQUE (company_id, id, routing_revision_id),
    FOREIGN KEY (company_id, routing_revision_id) REFERENCES routing_revision (company_id, id),
    FOREIGN KEY (company_id, work_center_id) REFERENCES work_center (company_id, id),
    FOREIGN KEY (company_id, service_item_id) REFERENCES item (company_id, id),
    FOREIGN KEY (company_id, default_supplier_id) REFERENCES partner (company_id, id),
    CONSTRAINT fk_routing_operation_sizing FOREIGN KEY (company_id, sizing_attribute_id, sizing_value_type) REFERENCES variant_attribute (company_id, id, value_type),
    CONSTRAINT ck_routing_operation_control_fields CHECK (CASE control
        WHEN 'internal' THEN work_center_id IS NOT NULL AND service_item_id IS NULL AND default_supplier_id IS NULL
        ELSE service_item_id IS NOT NULL AND default_supplier_id IS NOT NULL END),
    CONSTRAINT ck_routing_operation_sizing CHECK ((sizing_attribute_id IS NULL) = (setup_duration_per_value IS NULL AND run_duration_per_value IS NULL))
);
CREATE TABLE routing_operation_activity (                  -- standard activity quantities, inside the revision and its hash (rule 10)
    company_id            uuid NOT NULL,
    routing_operation_id  uuid NOT NULL,
    routing_revision_id   uuid NOT NULL,                       -- carried so the revision trigger needs one lookup
    activity_type_id      uuid NOT NULL,
    quantity              types.quantity NOT NULL CONSTRAINT ck_routing_operation_activity_quantity CHECK (quantity >= 0),
    basis                 text NOT NULL CONSTRAINT ck_routing_operation_activity_basis CHECK (basis IN ('per_order', 'per_base_quantity')),
    recorded_at           timestamptz NOT NULL,
    PRIMARY KEY (routing_operation_id, activity_type_id),
    FOREIGN KEY (company_id, routing_operation_id, routing_revision_id) REFERENCES routing_operation (company_id, id, routing_revision_id),
    FOREIGN KEY (company_id, activity_type_id) REFERENCES activity_type (company_id, id)
);
CREATE TABLE production_version (                          -- the one explicit way to make an item in a production warehouse (ADR-0033 rule 13)
    id                                uuid PRIMARY KEY,
    company_id                        uuid NOT NULL,
    item_id                           uuid,
    product_id                        uuid,                    -- a configurable product, exclusive with item_id (ADR-0046 rule 12)
    production_warehouse_id           uuid NOT NULL,
    code                              text NOT NULL,
    bill_of_materials_id              uuid NOT NULL,
    bill_of_materials_usage           text NOT NULL DEFAULT 'production' CONSTRAINT ck_production_version_usage CHECK (bill_of_materials_usage = 'production'),
    routing_id                        uuid,
    minimum_lot_quantity              types.quantity NOT NULL DEFAULT 0 CONSTRAINT ck_production_version_minimum_lot CHECK (minimum_lot_quantity >= 0),
    maximum_lot_quantity              types.quantity,          -- null = unbounded
    start_date                        date NOT NULL,
    end_date                          date,
    priority                          integer NOT NULL DEFAULT 0,   -- lowest first, then lowest code
    is_active                         boolean NOT NULL DEFAULT true,
    overdelivery_tolerance_percent    types.percent NOT NULL DEFAULT 0 CONSTRAINT ck_production_version_tolerance CHECK (overdelivery_tolerance_percent >= 0),   -- flagged default (ADR-0034 rule 13)
    is_receipt_on_final_confirmation  boolean NOT NULL DEFAULT false,
    is_complete_on_full_receipt       boolean NOT NULL DEFAULT false,
    is_as_built_required              boolean NOT NULL DEFAULT false,
    production_lead_time_method       text NOT NULL DEFAULT 'routing' CONSTRAINT ck_production_version_lead_time_method CHECK (production_lead_time_method IN ('fixed', 'routing')),
    production_lead_time_days         integer CONSTRAINT ck_production_version_lead_time_days CHECK (production_lead_time_days >= 0),   -- working days of the warehouse calendar
    recorded_at                       timestamptz NOT NULL,
    UNIQUE NULLS NOT DISTINCT (company_id, item_id, product_id, production_warehouse_id, code),
    UNIQUE (company_id, id),
    UNIQUE (company_id, id, production_warehouse_id),
    FOREIGN KEY (company_id, item_id) REFERENCES item (company_id, id),
    FOREIGN KEY (company_id, product_id) REFERENCES product (company_id, id),
    FOREIGN KEY (company_id, production_warehouse_id) REFERENCES warehouse (company_id, id),
    CONSTRAINT fk_production_version_bill FOREIGN KEY (company_id, bill_of_materials_id, bill_of_materials_usage) REFERENCES bill_of_materials (company_id, id, usage),
    FOREIGN KEY (company_id, routing_id) REFERENCES routing (company_id, id),
    CONSTRAINT ck_production_version_target CHECK ((item_id IS NULL) <> (product_id IS NULL)),
    CONSTRAINT ck_production_version_lot_range CHECK (maximum_lot_quantity IS NULL OR maximum_lot_quantity >= minimum_lot_quantity),
    CONSTRAINT ck_production_version_dates CHECK (end_date IS NULL OR end_date >= start_date),
    CONSTRAINT ck_production_version_lead_time CHECK ((production_lead_time_method = 'fixed') = (production_lead_time_days IS NOT NULL))
);
CREATE TABLE item_production_setting (                     -- ADR-0033 rule 14
    company_id               uuid NOT NULL,
    item_id                  uuid NOT NULL,
    production_warehouse_id  uuid NOT NULL,
    is_phantom               boolean NOT NULL DEFAULT false,
    recorded_at              timestamptz NOT NULL,
    PRIMARY KEY (item_id, production_warehouse_id),
    FOREIGN KEY (company_id, item_id) REFERENCES item (company_id, id),
    FOREIGN KEY (company_id, production_warehouse_id) REFERENCES warehouse (company_id, id)
);
CREATE TABLE item_low_level_code (                         -- read model owned by production, recomputed at release (ADR-0033 rule 8)
    company_id      uuid NOT NULL,
    item_id         uuid,
    product_id      uuid,                                      -- holistic decision 6: a configurable product is a node; its configured items inherit its code (ADR-0033 rule 8 note)
    low_level_code  integer NOT NULL CONSTRAINT ck_item_low_level_code_value CHECK (low_level_code >= 0),   -- 0 for top items; items without a row plan as 0 (ADR-0036 rule 2)
    recorded_at     timestamptz NOT NULL,
    FOREIGN KEY (company_id, item_id) REFERENCES item (company_id, id),
    FOREIGN KEY (company_id, product_id) REFERENCES product (company_id, id),
    CONSTRAINT ck_item_low_level_code_node CHECK ((item_id IS NULL) <> (product_id IS NULL))
);
CREATE UNIQUE INDEX ux_item_low_level_code_item ON item_low_level_code (company_id, item_id) WHERE item_id IS NOT NULL;
CREATE UNIQUE INDEX ux_item_low_level_code_product ON item_low_level_code (company_id, product_id) WHERE product_id IS NOT NULL;

-- ===== Planned orders, pegging, messages and exceptions [planning] (ADR-0024 rules 18-21; ADR-0036 rules 4-5) =====
CREATE TABLE planned_order (
    id                         uuid PRIMARY KEY,
    company_id                 uuid NOT NULL,
    item_id                    uuid NOT NULL,
    warehouse_id               uuid NOT NULL,
    order_type                 text NOT NULL CONSTRAINT ck_planned_order_type CHECK (order_type IN ('purchase', 'transfer', 'production')),
    supplier_partner_id        uuid,                           -- source of a purchase
    transfer_route_id          uuid,                           -- source of a transfer
    need_date                  date,                           -- null for reorder_point and min_max proposals (rule 18)
    for_demand_supply_line_id  uuid,                           -- make_to_order: the sales demand line is part of the key (ADR-0036 rule 4)
    sequence                   integer NOT NULL DEFAULT 1 CONSTRAINT ck_planned_order_sequence CHECK (sequence > 0),
    quantity                   types.quantity NOT NULL CONSTRAINT ck_planned_order_quantity CHECK (quantity > 0),   -- inventory unit
    -- the order unit block (ADR-0056 rules 9, 14): a purchase proposal in the supplier's order unit after minimum and multiple;
    -- transfer and production proposals in the inventory unit (identity)
    order_quantity             types.quantity NOT NULL CONSTRAINT ck_planned_order_order_quantity CHECK (order_quantity > 0),
    order_uom_id               uuid NOT NULL REFERENCES uom (id),
    uom_numerator              bigint NOT NULL,
    uom_denominator            bigint NOT NULL,
    uom_factor_source          text NOT NULL,
    rounding_excess_quantity   types.quantity NOT NULL DEFAULT 0 CONSTRAINT ck_planned_order_rounding_excess CHECK (rounding_excess_quantity >= 0),   -- shown on the proposal (rule 6)
    release_date               date NOT NULL,
    state                      text NOT NULL DEFAULT 'proposed' CONSTRAINT ck_planned_order_state CHECK (state IN ('proposed', 'firmed', 'converted', 'canceled')),
    production_version_id      uuid,                           -- an attribute, not part of the key (ADR-0036 rule 4)
    planned_start_date         date,
    planned_end_date           date,
    availability_date          date,                           -- planned end + the node's receiving_days
    planning_run_id            uuid NOT NULL,                  -- interim: not stated in ADR-0024 (the run that last created or updated it; listed with the run's results)
    recorded_at                timestamptz NOT NULL,
    UNIQUE (company_id, id),
    -- the business key; a canceled row never blocks a new proposal, which takes the next sequence (rule 18)
    UNIQUE NULLS NOT DISTINCT (company_id, item_id, warehouse_id, order_type, supplier_partner_id, transfer_route_id, need_date, for_demand_supply_line_id, sequence),
    FOREIGN KEY (company_id, item_id) REFERENCES item (company_id, id),
    FOREIGN KEY (company_id, warehouse_id) REFERENCES warehouse (company_id, id),
    FOREIGN KEY (company_id, supplier_partner_id) REFERENCES partner (company_id, id),
    CONSTRAINT fk_planned_order_route FOREIGN KEY (company_id, transfer_route_id, warehouse_id) REFERENCES transfer_route (company_id, id, destination_warehouse_id),
    FOREIGN KEY (company_id, for_demand_supply_line_id) REFERENCES demand_supply_line (company_id, id),
    -- the version makes in this warehouse; item-level or product-level, so the item is a command check
    CONSTRAINT fk_planned_order_version FOREIGN KEY (company_id, production_version_id, warehouse_id) REFERENCES production_version (company_id, id, production_warehouse_id),
    FOREIGN KEY (company_id, planning_run_id) REFERENCES planning_run (company_id, id),
    CONSTRAINT ck_planned_order_source CHECK ((order_type = 'purchase') = (supplier_partner_id IS NOT NULL) AND (order_type = 'transfer') = (transfer_route_id IS NOT NULL)),
    CONSTRAINT ck_planned_order_production CHECK ((order_type = 'production') = (production_version_id IS NOT NULL AND planned_start_date IS NOT NULL
                                                   AND planned_end_date IS NOT NULL AND availability_date IS NOT NULL)),
    CONSTRAINT ck_planned_order_production_dates CHECK (order_type <> 'production' OR (planned_end_date >= planned_start_date
                                                         AND availability_date >= planned_end_date AND release_date <= planned_start_date)),
    CONSTRAINT ck_planned_order_make_to_order CHECK (for_demand_supply_line_id IS NULL OR (order_type = 'production' AND need_date IS NOT NULL)),
    -- the line unit block (ADR-0056 rule 9): a known source, identity only at 1/1, and the inventory quantity within two
    -- inventory units of the exact conversion: a gross-error check that per-line rounding, the clamped forward parts and the
    -- returns' shares of a part (rule 10) provably keep
    CONSTRAINT ck_planned_order_uom_factor CHECK (uom_numerator > 0 AND uom_denominator > 0 AND uom_factor_source IN ('identity', 'item', 'product', 'global')
        AND (uom_factor_source <> 'identity' OR (uom_numerator = 1 AND uom_denominator = 1))),
    CONSTRAINT ck_planned_order_uom_quantity CHECK (abs(quantity * uom_denominator - order_quantity * uom_numerator) <= 2 * uom_denominator
        AND (uom_factor_source <> 'identity' OR quantity = order_quantity))
);
-- One open proposal per key without need_date (reorder_point and min_max, rule 18).
CREATE UNIQUE INDEX ux_planned_order_open_without_need_date ON planned_order (company_id, item_id, warehouse_id, order_type, supplier_partner_id, transfer_route_id)
    NULLS NOT DISTINCT WHERE need_date IS NULL AND state IN ('proposed', 'firmed');
ALTER TABLE demand_supply_line ADD CONSTRAINT fk_demand_supply_line_origin_planned_order FOREIGN KEY (company_id, origin_planned_order_id) REFERENCES planned_order (company_id, id);
CREATE TABLE planned_order_component (                     -- dependent demand, rewritten by each run and by UpdatePlannedOrder (ADR-0036 rule 5)
    id                 uuid PRIMARY KEY,
    company_id         uuid NOT NULL,
    planned_order_id   uuid NOT NULL,
    line_number        integer NOT NULL CONSTRAINT ck_planned_order_component_line CHECK (line_number > 0),
    component_item_id  uuid NOT NULL,
    warehouse_id       uuid NOT NULL,                          -- the production warehouse, or a processor location (ADR-0037 rule 2)
    quantity           types.quantity NOT NULL CONSTRAINT ck_planned_order_component_quantity CHECK (quantity > 0),   -- rounded up once per line (ADR-0033 rule 6)
    requested_date     date NOT NULL,                          -- scheduled start of the consuming operation
    operation_number   integer CONSTRAINT ck_planned_order_component_operation CHECK (operation_number > 0),
    recorded_at        timestamptz NOT NULL,
    UNIQUE (planned_order_id, line_number),
    UNIQUE (company_id, id),
    UNIQUE (company_id, id, planned_order_id),
    FOREIGN KEY (company_id, planned_order_id) REFERENCES planned_order (company_id, id),
    FOREIGN KEY (company_id, component_item_id) REFERENCES item (company_id, id),
    FOREIGN KEY (company_id, warehouse_id) REFERENCES warehouse (company_id, id)
);
CREATE TABLE planned_order_operation (                     -- the operation schedule of rule 3's function (ADR-0036 rule 4)
    company_id            uuid NOT NULL,
    planned_order_id      uuid NOT NULL,
    operation_number      integer NOT NULL CONSTRAINT ck_planned_order_operation_number CHECK (operation_number > 0),
    work_center_id        uuid,                                -- null for external operations, which load no work center
    control               text NOT NULL CONSTRAINT ck_planned_order_operation_control CHECK (control IN ('internal', 'external')),
    scheduled_start_date  date NOT NULL,
    scheduled_end_date    date NOT NULL,
    load_hours            numeric(14,4) NOT NULL DEFAULT 0 CONSTRAINT ck_planned_order_operation_load CHECK (load_hours >= 0),   -- interim: not stated in ADR-0036 (setup + run hours for ListCapacityLoad)
    recorded_at           timestamptz NOT NULL,
    PRIMARY KEY (planned_order_id, operation_number),
    FOREIGN KEY (company_id, planned_order_id) REFERENCES planned_order (company_id, id),
    FOREIGN KEY (company_id, work_center_id) REFERENCES work_center (company_id, id),
    CONSTRAINT ck_planned_order_operation_dates CHECK (scheduled_end_date >= scheduled_start_date),
    CONSTRAINT ck_planned_order_operation_internal CHECK (control = 'external' OR work_center_id IS NOT NULL)
);
CREATE TABLE planned_order_pegging (                       -- a planned order's pegging sums exactly to its quantity (INV-60, a run check); rules 20 and ADR-0036 rule 5
    id                           uuid PRIMARY KEY,
    company_id                   uuid NOT NULL,
    planned_order_id             uuid NOT NULL,
    pegging_target_kind          text NOT NULL CONSTRAINT ck_planned_order_pegging_target_kind CHECK (pegging_target_kind IN (
                                     'demand_line', 'forecast', 'safety_stock', 'stock_level', 'lot_size_excess', 'planned_order')),
    demand_supply_line_id        uuid,                         -- demand_line (ADR-0028 rule 2)
    target_planned_order_id      uuid,                         -- planned_order: the planned transfer or production order whose dependent demand this covers
    planned_order_component_id   uuid,                         -- planned_order through a bill of materials edge: its component line
    forecast_date                date,                         -- interim: not stated in ADR-0024 (the forecast day a forecast peg covers)
    quantity                     types.quantity NOT NULL CONSTRAINT ck_planned_order_pegging_quantity CHECK (quantity > 0),
    recorded_at                  timestamptz NOT NULL,
    FOREIGN KEY (company_id, planned_order_id) REFERENCES planned_order (company_id, id),
    FOREIGN KEY (company_id, demand_supply_line_id) REFERENCES demand_supply_line (company_id, id),
    FOREIGN KEY (company_id, target_planned_order_id) REFERENCES planned_order (company_id, id),
    -- the component line belongs to the target planned order
    CONSTRAINT fk_planned_order_pegging_component FOREIGN KEY (company_id, planned_order_component_id, target_planned_order_id) REFERENCES planned_order_component (company_id, id, planned_order_id),
    CONSTRAINT ck_planned_order_pegging_target CHECK ((pegging_target_kind = 'demand_line') = (demand_supply_line_id IS NOT NULL)
        AND (pegging_target_kind = 'planned_order') = (target_planned_order_id IS NOT NULL)
        AND (pegging_target_kind = 'forecast') = (forecast_date IS NOT NULL)
        AND (planned_order_component_id IS NULL OR pegging_target_kind = 'planned_order')),
    CONSTRAINT ck_planned_order_pegging_not_self CHECK (target_planned_order_id IS DISTINCT FROM planned_order_id)
);
CREATE INDEX ix_planned_order_pegging_planned_order_id ON planned_order_pegging (planned_order_id);
CREATE TABLE planning_action_message (                     -- on existing supply, with its projected effect (rule 21); table named by the holistic review
    id                     uuid PRIMARY KEY,
    company_id             uuid NOT NULL,
    planning_run_id        uuid NOT NULL,
    kind                   text NOT NULL CONSTRAINT ck_planning_action_message_kind CHECK (kind IN ('expedite', 'cancel', 'postpone', 'reduce')),   -- postpone and reduce: later slice
    demand_supply_line_id  uuid NOT NULL,                      -- the supply line it acts on
    requested_date         date NOT NULL,                      -- the supply's current date
    proposed_date          date,
    proposed_quantity      types.quantity CONSTRAINT ck_planning_action_message_proposed_quantity CHECK (proposed_quantity >= 0),
    projected_effect       jsonb NOT NULL,
    recorded_at            timestamptz NOT NULL,
    FOREIGN KEY (company_id, planning_run_id) REFERENCES planning_run (company_id, id),
    FOREIGN KEY (company_id, demand_supply_line_id) REFERENCES demand_supply_line (company_id, id),
    CONSTRAINT ck_planning_action_message_fields CHECK (CASE kind
        WHEN 'expedite' THEN proposed_date < requested_date AND proposed_quantity IS NULL
        WHEN 'postpone' THEN proposed_date > requested_date AND proposed_quantity IS NULL
        WHEN 'reduce'   THEN proposed_quantity IS NOT NULL AND proposed_date IS NULL
        ELSE proposed_date IS NULL AND proposed_quantity IS NULL END)
);
CREATE TABLE planning_exception (                          -- one work item per open exception, closed when a run no longer raises it (rule 21; ADR-0031 rule 17)
    id                     uuid PRIMARY KEY,
    company_id             uuid NOT NULL,
    planning_run_id        uuid NOT NULL,                      -- the run that last raised it
    kind                   text NOT NULL CONSTRAINT ck_planning_exception_kind CHECK (kind IN (
                               'shortage_inside_lead_time', 'below_safety_stock', 'above_maximum', 'supplier_minimum_excess',
                               'below_supplier_minimum_amount', 'container_underfilled', 'stock_expiring', 'firmed_order_overdue',
                               'planning_parameter_missing', 'capacity_overload')),
    -- interim: not stated in ADR-0024 (the reasons named in ADR-0024 rule 21 and ADR-0036 rules 1, 4, 5 as values)
    reason                 text CONSTRAINT ck_planning_exception_reason CHECK (reason IN (
                               'planning_row_missing', 'supplier_missing', 'preferred_supplier_ambiguous', 'route_missing', 'lead_time_missing',
                               'production_version_missing', 'production_version_invalid', 'phantom_with_demand')),
    exception_key          text NOT NULL,                      -- interim: not stated in ADR-0024 (canonical key a run uses to find and close its exception)
    item_id                uuid,
    warehouse_id           uuid,
    supplier_partner_id    uuid,                               -- supplier-level exceptions
    work_center_id         uuid,                               -- capacity_overload
    start_date             date,                               -- capacity_overload: the overloaded range of buckets
    end_date               date,
    planned_order_id       uuid,
    demand_supply_line_id  uuid,                               -- the demand that hit a missing parameter (ADR-0036 rule 1)
    lateness_days          integer CONSTRAINT ck_planning_exception_lateness CHECK (lateness_days > 0),
    evidence               jsonb NOT NULL DEFAULT '{}',
    state                  text NOT NULL DEFAULT 'open' CONSTRAINT ck_planning_exception_state CHECK (state IN ('open', 'closed')),
    closed_at              timestamptz,
    recorded_at            timestamptz NOT NULL,
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, planning_run_id) REFERENCES planning_run (company_id, id),
    FOREIGN KEY (company_id, item_id) REFERENCES item (company_id, id),
    FOREIGN KEY (company_id, warehouse_id) REFERENCES warehouse (company_id, id),
    FOREIGN KEY (company_id, supplier_partner_id) REFERENCES partner (company_id, id),
    FOREIGN KEY (company_id, work_center_id) REFERENCES work_center (company_id, id),
    FOREIGN KEY (company_id, planned_order_id) REFERENCES planned_order (company_id, id),
    FOREIGN KEY (company_id, demand_supply_line_id) REFERENCES demand_supply_line (company_id, id),
    CONSTRAINT ck_planning_exception_reason_kind CHECK ((kind = 'planning_parameter_missing') = (reason IS NOT NULL)),
    CONSTRAINT ck_planning_exception_subject CHECK (CASE
        WHEN kind = 'capacity_overload' THEN work_center_id IS NOT NULL AND start_date IS NOT NULL AND coalesce(end_date >= start_date, false)
        WHEN kind IN ('below_supplier_minimum_amount', 'container_underfilled') THEN supplier_partner_id IS NOT NULL
        ELSE item_id IS NOT NULL AND warehouse_id IS NOT NULL END),
    CONSTRAINT ck_planning_exception_closed CHECK ((state = 'closed') = (closed_at IS NOT NULL))
);
CREATE UNIQUE INDEX ux_planning_exception_open ON planning_exception (company_id, exception_key) WHERE state = 'open';

-- ===== Replenishment hand-over [inventory] (ADR-0024 rule 22) =====
-- Written by inventory.contract.request_replenishment, one line per converted purchase or transfer planned order;
-- ReplenishmentRequested follows. Production planned orders convert through production.contract instead.
-- The line copies what purchasing and inventory need, so neither imports planning (ADR-0022 rule 2).
CREATE TABLE replenishment_request (
    id                    uuid PRIMARY KEY,
    company_id            uuid NOT NULL REFERENCES company (id),
    requested_by_user_id  uuid NOT NULL REFERENCES user_account (id),   -- the converter
    recorded_at           timestamptz NOT NULL,
    UNIQUE (company_id, id)
);
CREATE TABLE replenishment_request_line (
    company_id                uuid NOT NULL,
    replenishment_request_id  uuid NOT NULL,
    line_number               integer NOT NULL CONSTRAINT ck_replenishment_request_line_number CHECK (line_number > 0),
    origin_planned_order_id   uuid NOT NULL UNIQUE,            -- a planned order converts whole, once
    -- interim: not stated in ADR-0024 (the copied planned order fields below)
    item_id                   uuid NOT NULL,
    warehouse_id              uuid NOT NULL,
    order_type                text NOT NULL CONSTRAINT ck_replenishment_request_line_type CHECK (order_type IN ('purchase', 'transfer')),
    supplier_partner_id       uuid,
    transfer_route_id         uuid,
    quantity                  types.quantity NOT NULL CONSTRAINT ck_replenishment_request_line_quantity CHECK (quantity > 0),   -- in uom_id, the planned order's order unit
    uom_id                    uuid NOT NULL REFERENCES uom (id),
    uom_numerator             bigint NOT NULL,                  -- the conversion snapshot: 1 uom_id = uom_numerator / uom_denominator
    uom_denominator           bigint NOT NULL,                  -- inventory units, taken when the unit was set, never re-read (ADR-0056 rule 9)
    uom_factor_source         text NOT NULL,                    -- identity, item, product or global (ADR-0056 rule 6)
    inventory_quantity        types.quantity NOT NULL CONSTRAINT ck_replenishment_request_line_inventory_quantity CHECK (inventory_quantity > 0),
    need_date                 date,
    release_date              date NOT NULL,
    recorded_at               timestamptz NOT NULL,
    PRIMARY KEY (replenishment_request_id, line_number),
    FOREIGN KEY (company_id, replenishment_request_id) REFERENCES replenishment_request (company_id, id),
    FOREIGN KEY (company_id, origin_planned_order_id) REFERENCES planned_order (company_id, id),
    FOREIGN KEY (company_id, item_id) REFERENCES item (company_id, id),
    FOREIGN KEY (company_id, warehouse_id) REFERENCES warehouse (company_id, id),
    FOREIGN KEY (company_id, supplier_partner_id) REFERENCES partner (company_id, id),
    CONSTRAINT fk_replenishment_request_line_route FOREIGN KEY (company_id, transfer_route_id, warehouse_id) REFERENCES transfer_route (company_id, id, destination_warehouse_id),
    CONSTRAINT ck_replenishment_request_line_source CHECK ((order_type = 'purchase') = (supplier_partner_id IS NOT NULL) AND (order_type = 'transfer') = (transfer_route_id IS NOT NULL)),
    -- the line unit block (ADR-0056 rule 9): a known source, identity only at 1/1, and the inventory quantity within two
    -- inventory units of the exact conversion: a gross-error check that per-line rounding, the clamped forward parts and the
    -- returns' shares of a part (rule 10) provably keep
    CONSTRAINT ck_replenishment_request_line_uom_factor CHECK (uom_numerator > 0 AND uom_denominator > 0 AND uom_factor_source IN ('identity', 'item', 'product', 'global')
        AND (uom_factor_source <> 'identity' OR (uom_numerator = 1 AND uom_denominator = 1))),
    CONSTRAINT ck_replenishment_request_line_uom_quantity CHECK (abs(inventory_quantity * uom_denominator - quantity * uom_numerator) <= 2 * uom_denominator
        AND (uom_factor_source <> 'identity' OR inventory_quantity = quantity))
);

-- ===== Production orders [production] (ADR-0034 rules 1-10, 14-16) =====
CREATE TABLE production_order (                            -- typed header of a non-posting document type with change orders (rule 1)
    id                              uuid PRIMARY KEY,
    company_id                      uuid NOT NULL,
    order_type                      text NOT NULL CONSTRAINT ck_production_order_type CHECK (order_type IN ('standard', 'rework', 'disassembly')),
    item_id                         uuid NOT NULL,
    production_warehouse_id         uuid NOT NULL,             -- the record scope's warehouse dimension (rule 18)
    production_version_id           uuid,                      -- standard and disassembly; a rework order has no explosion (rule 4)
    bill_of_materials_revision_id   uuid,                      -- snapshot at the explosion date
    routing_revision_id             uuid,
    product_configuration_id        uuid,                      -- a configured item's configuration (ADR-0046 rule 13)
    good_quantity                   types.quantity NOT NULL CONSTRAINT ck_production_order_good_quantity CHECK (good_quantity > 0),   -- G
    planned_output_quantity         types.quantity NOT NULL,   -- Q = G / (1 - assembly scrap)
    planned_start_date              date NOT NULL,             -- the explosion_date
    planned_end_date                date NOT NULL,
    scheduling_direction            text NOT NULL DEFAULT 'forward' CONSTRAINT ck_production_order_scheduling CHECK (scheduling_direction IN ('forward', 'backward')),
    cost_object_id                  uuid,                      -- set at release (rule 15); key added below, to DS-06's composite key
    origin_planned_order_id         uuid,                      -- DS-54
    for_demand_supply_line_id       uuid,                      -- B3, interim: make to order (rule 14)
    overdelivery_tolerance_percent  types.percent NOT NULL DEFAULT 0 CONSTRAINT ck_production_order_tolerance CHECK (overdelivery_tolerance_percent >= 0),
    execution_state                 text NOT NULL DEFAULT 'not_started' CONSTRAINT ck_production_order_execution_state CHECK (execution_state IN ('not_started', 'in_progress', 'technically_complete')),
    is_content_edited               boolean NOT NULL DEFAULT false,   -- lines edited by hand: re-explosion scales instead (rule 2)
    recorded_at                     timestamptz NOT NULL,
    UNIQUE (company_id, id),
    UNIQUE (company_id, id, cost_object_id),
    FOREIGN KEY (company_id, id) REFERENCES document (company_id, id),
    FOREIGN KEY (company_id, item_id) REFERENCES item (company_id, id),
    FOREIGN KEY (company_id, production_warehouse_id) REFERENCES warehouse (company_id, id),
    CONSTRAINT fk_production_order_version FOREIGN KEY (company_id, production_version_id, production_warehouse_id) REFERENCES production_version (company_id, id, production_warehouse_id),
    FOREIGN KEY (company_id, bill_of_materials_revision_id) REFERENCES bill_of_materials_revision (company_id, id),
    FOREIGN KEY (company_id, routing_revision_id) REFERENCES routing_revision (company_id, id),
    FOREIGN KEY (company_id, origin_planned_order_id) REFERENCES planned_order (company_id, id),
    FOREIGN KEY (company_id, for_demand_supply_line_id) REFERENCES demand_supply_line (company_id, id),
    FOREIGN KEY (company_id, product_configuration_id) REFERENCES product_configuration (company_id, id),
    CONSTRAINT ck_production_order_version CHECK (order_type = 'rework' OR (production_version_id IS NOT NULL AND bill_of_materials_revision_id IS NOT NULL)),
    CONSTRAINT ck_production_order_planned_output CHECK (planned_output_quantity >= good_quantity),
    CONSTRAINT ck_production_order_dates CHECK (planned_end_date >= planned_start_date)
);
CREATE UNIQUE INDEX ux_production_order_origin_planned_order ON production_order (origin_planned_order_id) WHERE origin_planned_order_id IS NOT NULL;
CREATE TABLE production_order_component (                  -- rule 1; external-operation components at the processor location (ADR-0037 rule 2)
    id                     uuid PRIMARY KEY,
    company_id             uuid NOT NULL,
    production_order_id    uuid NOT NULL,
    line_number            integer NOT NULL CONSTRAINT ck_production_order_component_line CHECK (line_number > 0),
    component_item_id      uuid NOT NULL,
    required_quantity      types.quantity NOT NULL CONSTRAINT ck_production_order_component_required CHECK (required_quantity >= 0),   -- inventory unit, rounded up once
    issue_warehouse_id     uuid NOT NULL,                      -- default the production warehouse
    operation_number       integer CONSTRAINT ck_production_order_component_operation CHECK (operation_number > 0),
    consumption_method     text NOT NULL CONSTRAINT ck_production_order_component_consumption CHECK (consumption_method IN ('manual', 'backflush_at_operation', 'backflush_at_receipt')),
    is_fixed_quantity      boolean NOT NULL DEFAULT false,
    phantom_path           uuid[] NOT NULL DEFAULT '{}',       -- the phantom bill of materials component lines it came through
    requested_date         date NOT NULL,
    owner_partner_id       uuid,                               -- B3, interim: reserved owner axis (ADR-0037 rule 7)
    recorded_at            timestamptz NOT NULL,
    UNIQUE (production_order_id, line_number),
    UNIQUE (company_id, id),
    -- posted lines keep item and warehouse (referenced_line_immutable, rule 8), so issue lines may key on them
    UNIQUE (company_id, id, production_order_id, component_item_id, issue_warehouse_id),
    UNIQUE (company_id, id, production_order_id),
    FOREIGN KEY (company_id, production_order_id) REFERENCES production_order (company_id, id),
    FOREIGN KEY (company_id, component_item_id) REFERENCES item (company_id, id),
    FOREIGN KEY (company_id, issue_warehouse_id) REFERENCES warehouse (company_id, id),
    FOREIGN KEY (company_id, owner_partner_id) REFERENCES partner (company_id, id)
);
CREATE TABLE production_order_output (                     -- main output (planned quantity G), co-products and by-products (rule 1)
    id                   uuid PRIMARY KEY,
    company_id           uuid NOT NULL,
    production_order_id  uuid NOT NULL,
    line_number          integer NOT NULL CONSTRAINT ck_production_order_output_line CHECK (line_number > 0),
    output_item_id       uuid NOT NULL,
    output_type          text NOT NULL CONSTRAINT ck_production_order_output_type CHECK (output_type IN ('main', 'co_product', 'by_product')),   -- interim: not stated in ADR-0034 (the value 'main')
    planned_quantity     types.quantity NOT NULL CONSTRAINT ck_production_order_output_quantity CHECK (planned_quantity >= 0),
    cost_coefficient     numeric(18,6),
    requested_date       date NOT NULL,                        -- the order's end
    owner_partner_id     uuid,                                 -- B3, interim (ADR-0037 rule 7)
    recorded_at          timestamptz NOT NULL,
    UNIQUE (production_order_id, line_number),
    UNIQUE (company_id, id),
    UNIQUE (company_id, id, production_order_id, output_item_id),
    UNIQUE (company_id, id, production_order_id),
    FOREIGN KEY (company_id, production_order_id) REFERENCES production_order (company_id, id),
    FOREIGN KEY (company_id, output_item_id) REFERENCES item (company_id, id),
    FOREIGN KEY (company_id, owner_partner_id) REFERENCES partner (company_id, id),
    CONSTRAINT ck_production_order_output_coefficient CHECK (coalesce(cost_coefficient, 0) >= 0 AND (cost_coefficient IS NULL OR output_type <> 'by_product'))
);
-- At most one main output; a disassembly order has co_product outputs only (rule 4).
CREATE UNIQUE INDEX ux_production_order_output_main ON production_order_output (production_order_id) WHERE output_type = 'main';
CREATE TABLE production_order_operation (                  -- copied from the routing revision (rule 1); external: chosen supplier (ADR-0037 rule 2)
    id                       uuid PRIMARY KEY,
    company_id               uuid NOT NULL,
    production_order_id      uuid NOT NULL,
    line_number              integer NOT NULL CONSTRAINT ck_production_order_operation_line CHECK (line_number > 0),
    operation_number         integer NOT NULL CONSTRAINT ck_production_order_operation_number CHECK (operation_number > 0),
    work_center_id           uuid,
    control                  text NOT NULL CONSTRAINT ck_production_order_operation_control CHECK (control IN ('internal', 'external')),
    supplier_partner_id      uuid,                             -- external: the chosen supplier
    service_item_id          uuid,                             -- external
    is_milestone             boolean NOT NULL DEFAULT false,
    setup_duration           numeric(12,4) NOT NULL DEFAULT 0 CONSTRAINT ck_production_order_operation_setup CHECK (setup_duration >= 0),
    run_duration             numeric(12,4) NOT NULL DEFAULT 0 CONSTRAINT ck_production_order_operation_run CHECK (run_duration >= 0),
    operation_scrap_percent  types.percent NOT NULL DEFAULT 0 CONSTRAINT ck_production_order_operation_scrap CHECK (operation_scrap_percent >= 0 AND operation_scrap_percent < 100),
    queue_time               numeric(12,4) NOT NULL DEFAULT 0 CONSTRAINT ck_production_order_operation_queue CHECK (queue_time >= 0),
    move_time                numeric(12,4) NOT NULL DEFAULT 0 CONSTRAINT ck_production_order_operation_move CHECK (move_time >= 0),
    expected_quantity        types.quantity NOT NULL CONSTRAINT ck_production_order_operation_expected CHECK (expected_quantity >= 0),   -- for information
    scheduled_start_date     date NOT NULL,
    scheduled_end_date       date NOT NULL,
    recorded_at              timestamptz NOT NULL,
    UNIQUE (production_order_id, line_number),
    UNIQUE (production_order_id, operation_number),
    UNIQUE (company_id, id),
    UNIQUE (company_id, id, production_order_id),
    UNIQUE (company_id, id, production_order_id, control),
    FOREIGN KEY (company_id, production_order_id) REFERENCES production_order (company_id, id),
    FOREIGN KEY (company_id, work_center_id) REFERENCES work_center (company_id, id),
    FOREIGN KEY (company_id, supplier_partner_id) REFERENCES partner (company_id, id),
    FOREIGN KEY (company_id, service_item_id) REFERENCES item (company_id, id),
    CONSTRAINT ck_production_order_operation_control_fields CHECK (CASE control
        WHEN 'internal' THEN work_center_id IS NOT NULL AND supplier_partner_id IS NULL AND service_item_id IS NULL
        ELSE supplier_partner_id IS NOT NULL AND service_item_id IS NOT NULL END),
    CONSTRAINT ck_production_order_operation_dates CHECK (scheduled_end_date >= scheduled_start_date)
);
CREATE TABLE production_order_operation_activity (         -- activity standards copied with the operation (rule 1)
    company_id                     uuid NOT NULL,
    production_order_operation_id  uuid NOT NULL,
    activity_type_id               uuid NOT NULL,
    quantity                       types.quantity NOT NULL CONSTRAINT ck_production_order_operation_activity_quantity CHECK (quantity >= 0),
    basis                          text NOT NULL CONSTRAINT ck_production_order_operation_activity_basis CHECK (basis IN ('per_order', 'per_base_quantity')),
    recorded_at                    timestamptz NOT NULL,
    PRIMARY KEY (production_order_operation_id, activity_type_id),
    FOREIGN KEY (company_id, production_order_operation_id) REFERENCES production_order_operation (company_id, id),
    FOREIGN KEY (company_id, activity_type_id) REFERENCES activity_type (company_id, id)
);
CREATE TABLE production_order_output_serial (              -- assigned serials; not version content (rules 1, 16)
    company_id                  uuid NOT NULL,
    production_order_id         uuid NOT NULL,
    production_order_output_id  uuid NOT NULL,
    serial_number_id            uuid NOT NULL REFERENCES serial_number (id),
    assigned_at                 timestamptz NOT NULL,
    freed_at                    timestamptz,                   -- at technical completion or Cancel when not received
    recorded_at                 timestamptz NOT NULL,
    PRIMARY KEY (production_order_id, serial_number_id),
    CONSTRAINT fk_production_order_output_serial_output FOREIGN KEY (company_id, production_order_output_id, production_order_id) REFERENCES production_order_output (company_id, id, production_order_id),
    CONSTRAINT ck_production_order_output_serial_dates CHECK (freed_at IS NULL OR freed_at >= assigned_at)
);
-- A serial has at most one open assignment (rule 16).
CREATE UNIQUE INDEX ux_production_order_output_serial_open ON production_order_output_serial (serial_number_id) WHERE freed_at IS NULL;
-- The B3 keys of demand_supply_line to production lines (cycle-free load order: demand_supply_line comes first).
ALTER TABLE demand_supply_line ADD CONSTRAINT fk_demand_supply_line_component FOREIGN KEY (company_id, production_order_component_id) REFERENCES production_order_component (company_id, id);
ALTER TABLE demand_supply_line ADD CONSTRAINT fk_demand_supply_line_output FOREIGN KEY (company_id, production_order_output_id) REFERENCES production_order_output (company_id, id);

-- ===== Shop-floor posting documents [production] (ADR-0034 rules 11-13; internal, reversible) =====
-- Every material line carries its order's cost object (INV-103): the composite key to production_order on
-- (order, cost_object_id) holds it. Approval pools (ADR-0055 rule 2, holistic decision 12): production_issue maps to pool
-- consumption; operation_confirmation, production_receipt and service_receipt are facts with is_approval_hold_allowed false.
CREATE TABLE production_issue (
    id                   uuid PRIMARY KEY,
    company_id           uuid NOT NULL,
    production_order_id  uuid NOT NULL,
    posting_date         date NOT NULL,                        -- interim: not stated in ADR-0034 for the issue (as for the confirmation)
    recorded_at          timestamptz NOT NULL,
    UNIQUE (company_id, id),
    UNIQUE (company_id, id, production_order_id),
    FOREIGN KEY (company_id, id) REFERENCES document (company_id, id),
    FOREIGN KEY (company_id, production_order_id) REFERENCES production_order (company_id, id)
);
CREATE TABLE production_issue_line (
    id                             uuid PRIMARY KEY,
    company_id                     uuid NOT NULL,
    production_issue_id            uuid NOT NULL,
    production_order_id            uuid NOT NULL,              -- carried for the keys below
    line_number                    integer NOT NULL CONSTRAINT ck_production_issue_line_number CHECK (line_number > 0),
    production_order_component_id  uuid NOT NULL,
    item_id                        uuid NOT NULL,
    warehouse_id                   uuid NOT NULL,              -- interim: not stated in ADR-0034 (the component line's issue warehouse, for the bin key)
    quantity                       types.quantity NOT NULL CONSTRAINT ck_production_issue_line_quantity CHECK (quantity > 0),   -- as entered, in uom_id (ADR-0056 rule 9)
    uom_id                         uuid NOT NULL REFERENCES uom (id),
    uom_numerator                  bigint NOT NULL,             -- the conversion snapshot: 1 uom_id = uom_numerator / uom_denominator
    uom_denominator                bigint NOT NULL,             -- inventory units, taken when the unit was set, never re-read (ADR-0056 rule 9)
    uom_factor_source              text NOT NULL,               -- identity, item, product or global (ADR-0056 rule 6)
    inventory_quantity             types.quantity NOT NULL CONSTRAINT ck_production_issue_line_inventory_quantity CHECK (inventory_quantity > 0),
    lot_id                         uuid REFERENCES lot (id),
    serial_number_id               uuid REFERENCES serial_number (id),
    bin_id                         uuid NOT NULL,
    handling_unit_id               uuid,                       -- no DDL yet (DS-42)
    stock_status                   text NOT NULL DEFAULT 'available' CONSTRAINT ck_production_issue_line_status CHECK (stock_status IN ('available', 'quality_inspection')),   -- quality_inspection for rework
    is_return                      boolean NOT NULL DEFAULT false,
    output_serial_number_id        uuid,                       -- as built (rule 16)
    reason_code                    text,                       -- company data, for over-issue
    cost_object_id                 uuid NOT NULL,
    material_document_line_id      uuid REFERENCES material_document_line (id),   -- interim: not stated in ADR-0034 (the posted movement)
    recorded_at                    timestamptz NOT NULL,
    UNIQUE (production_issue_id, line_number),
    CONSTRAINT fk_production_issue_line_issue FOREIGN KEY (company_id, production_issue_id, production_order_id) REFERENCES production_issue (company_id, id, production_order_id),
    -- the component line is of the same order, with the same item and issue warehouse
    CONSTRAINT fk_production_issue_line_component FOREIGN KEY (company_id, production_order_component_id, production_order_id, item_id, warehouse_id)
        REFERENCES production_order_component (company_id, id, production_order_id, component_item_id, issue_warehouse_id),
    CONSTRAINT fk_production_issue_line_bin FOREIGN KEY (bin_id, warehouse_id) REFERENCES bin (id, warehouse_id),
    -- INV-103: the order's cost object
    CONSTRAINT fk_production_issue_line_cost_object FOREIGN KEY (company_id, production_order_id, cost_object_id) REFERENCES production_order (company_id, id, cost_object_id),
    -- INV-105: an output serial assigned to the same order
    CONSTRAINT fk_production_issue_line_output_serial FOREIGN KEY (production_order_id, output_serial_number_id) REFERENCES production_order_output_serial (production_order_id, serial_number_id),
    CONSTRAINT ck_production_issue_line_tracking CHECK (num_nonnulls(lot_id, serial_number_id) <= 1 AND (serial_number_id IS NULL OR inventory_quantity = 1)),
    -- the line unit block (ADR-0056 rule 9): a known source, identity only at 1/1, and the inventory quantity within two
    -- inventory units of the exact conversion: a gross-error check that per-line rounding, the clamped forward parts and the
    -- returns' shares of a part (rule 10) provably keep
    CONSTRAINT ck_production_issue_line_uom_factor CHECK (uom_numerator > 0 AND uom_denominator > 0 AND uom_factor_source IN ('identity', 'item', 'product', 'global')
        AND (uom_factor_source <> 'identity' OR (uom_numerator = 1 AND uom_denominator = 1))),
    CONSTRAINT ck_production_issue_line_uom_quantity CHECK (abs(inventory_quantity * uom_denominator - quantity * uom_numerator) <= 2 * uom_denominator
        AND (uom_factor_source <> 'identity' OR inventory_quantity = quantity))
);
CREATE TABLE operation_confirmation (                      -- an internal operation of the order (rule 12)
    id                             uuid PRIMARY KEY,
    company_id                     uuid NOT NULL,
    production_order_id            uuid NOT NULL,
    production_order_operation_id  uuid NOT NULL,
    operation_control              text NOT NULL DEFAULT 'internal' CONSTRAINT ck_operation_confirmation_control CHECK (operation_control = 'internal'),
    yield_quantity                 types.quantity NOT NULL CONSTRAINT ck_operation_confirmation_yield CHECK (yield_quantity >= 0),
    scrap_quantity                 types.quantity NOT NULL DEFAULT 0 CONSTRAINT ck_operation_confirmation_scrap CHECK (scrap_quantity >= 0),
    scrap_reason_code              text,
    is_final                       boolean NOT NULL DEFAULT false,
    lot_id                         uuid REFERENCES lot (id),   -- names the output lot for an automatic receipt (rule 13)
    employee_partner_id            uuid,                       -- interim: not stated in ADR-0034 ("optional people or teams": column names)
    team_id                        uuid,                       -- interim: not stated in ADR-0034
    posting_date                   date NOT NULL,
    recorded_at                    timestamptz NOT NULL,
    UNIQUE (company_id, id),
    UNIQUE (company_id, id, production_order_id),
    FOREIGN KEY (company_id, id) REFERENCES document (company_id, id),
    FOREIGN KEY (company_id, production_order_id) REFERENCES production_order (company_id, id),
    -- operation_not_confirmable: an internal operation of the same order
    CONSTRAINT fk_operation_confirmation_operation FOREIGN KEY (company_id, production_order_operation_id, production_order_id, operation_control)
        REFERENCES production_order_operation (company_id, id, production_order_id, control),
    FOREIGN KEY (company_id, employee_partner_id) REFERENCES partner (company_id, id),
    FOREIGN KEY (company_id, team_id) REFERENCES team (company_id, id),
    CONSTRAINT ck_operation_confirmation_scrap_reason CHECK (scrap_reason_code IS NULL OR scrap_quantity > 0)
);
CREATE TABLE operation_confirmation_activity (             -- actual activity quantities, defaulting to the standards (rule 12)
    company_id                 uuid NOT NULL,
    operation_confirmation_id  uuid NOT NULL,
    activity_type_id           uuid NOT NULL,
    quantity                   types.quantity NOT NULL CONSTRAINT ck_operation_confirmation_activity_quantity CHECK (quantity >= 0),
    recorded_at                timestamptz NOT NULL,
    PRIMARY KEY (operation_confirmation_id, activity_type_id),
    FOREIGN KEY (company_id, operation_confirmation_id) REFERENCES operation_confirmation (company_id, id),
    FOREIGN KEY (company_id, activity_type_id) REFERENCES activity_type (company_id, id)
);
CREATE TABLE production_receipt (                          -- rule 13
    id                         uuid PRIMARY KEY,
    company_id                 uuid NOT NULL,
    production_order_id        uuid NOT NULL,
    posting_date               date NOT NULL,                  -- interim: not stated in ADR-0034 for the receipt (as for the confirmation)
    operation_confirmation_id  uuid,                           -- interim: not stated in ADR-0034 (the confirmation whose final progress created this automatic receipt; reversed with it)
    service_receipt_id         uuid,                           -- interim: not stated in ADR-0037 (the same, for a service receipt; purchasing's document)
    recorded_at                timestamptz NOT NULL,
    UNIQUE (company_id, id),
    UNIQUE (company_id, id, production_order_id),
    FOREIGN KEY (company_id, id) REFERENCES document (company_id, id),
    FOREIGN KEY (company_id, production_order_id) REFERENCES production_order (company_id, id),
    CONSTRAINT fk_production_receipt_confirmation FOREIGN KEY (company_id, operation_confirmation_id, production_order_id) REFERENCES operation_confirmation (company_id, id, production_order_id),
    CONSTRAINT fk_production_receipt_service_receipt FOREIGN KEY (company_id, service_receipt_id) REFERENCES document (company_id, id),
    CONSTRAINT ck_production_receipt_trigger CHECK (num_nonnulls(operation_confirmation_id, service_receipt_id) <= 1)
);
CREATE TABLE production_receipt_line (
    id                          uuid PRIMARY KEY,
    company_id                  uuid NOT NULL,
    production_receipt_id       uuid NOT NULL,
    production_order_id         uuid NOT NULL,
    line_number                 integer NOT NULL CONSTRAINT ck_production_receipt_line_number CHECK (line_number > 0),
    production_order_output_id  uuid NOT NULL,
    item_id                     uuid NOT NULL,
    warehouse_id                uuid NOT NULL,                 -- interim: not stated in ADR-0034 (for the bin key)
    quantity                    types.quantity NOT NULL CONSTRAINT ck_production_receipt_line_quantity CHECK (quantity > 0),   -- as entered, in uom_id (ADR-0056 rule 9)
    uom_id                      uuid NOT NULL REFERENCES uom (id),
    uom_numerator               bigint NOT NULL,                -- the conversion snapshot: 1 uom_id = uom_numerator / uom_denominator
    uom_denominator             bigint NOT NULL,                -- inventory units, taken when the unit was set, never re-read (ADR-0056 rule 9)
    uom_factor_source           text NOT NULL,                  -- identity, item, product or global (ADR-0056 rule 6)
    inventory_quantity          types.quantity NOT NULL CONSTRAINT ck_production_receipt_line_inventory_quantity CHECK (inventory_quantity > 0),
    lot_id                      uuid REFERENCES lot (id),      -- created at receipt when lot-tracked
    serial_number_id            uuid,
    bin_id                      uuid NOT NULL,
    handling_unit_id            uuid,
    stock_status                text NOT NULL DEFAULT 'available' CONSTRAINT ck_production_receipt_line_status CHECK (stock_status IN ('available', 'quality_inspection')),
    movement_type               text NOT NULL CONSTRAINT ck_production_receipt_line_movement CHECK (movement_type IN ('production_receipt', 'co_product_receipt', 'by_product_receipt', 'disassembly_receipt')),
    cost_object_id              uuid NOT NULL,
    material_document_line_id   uuid REFERENCES material_document_line (id),   -- interim: not stated in ADR-0034
    recorded_at                 timestamptz NOT NULL,
    UNIQUE (production_receipt_id, line_number),
    CONSTRAINT fk_production_receipt_line_receipt FOREIGN KEY (company_id, production_receipt_id, production_order_id) REFERENCES production_receipt (company_id, id, production_order_id),
    CONSTRAINT fk_production_receipt_line_output FOREIGN KEY (company_id, production_order_output_id, production_order_id, item_id)
        REFERENCES production_order_output (company_id, id, production_order_id, output_item_id),
    CONSTRAINT fk_production_receipt_line_bin FOREIGN KEY (bin_id, warehouse_id) REFERENCES bin (id, warehouse_id),
    CONSTRAINT fk_production_receipt_line_cost_object FOREIGN KEY (company_id, production_order_id, cost_object_id) REFERENCES production_order (company_id, id, cost_object_id),
    -- received serials are serials assigned to the same order (rule 16)
    CONSTRAINT fk_production_receipt_line_serial FOREIGN KEY (production_order_id, serial_number_id) REFERENCES production_order_output_serial (production_order_id, serial_number_id),
    CONSTRAINT ck_production_receipt_line_tracking CHECK (num_nonnulls(lot_id, serial_number_id) <= 1 AND (serial_number_id IS NULL OR inventory_quantity = 1)),
    -- the line unit block (ADR-0056 rule 9): a known source, identity only at 1/1, and the inventory quantity within two
    -- inventory units of the exact conversion: a gross-error check that per-line rounding, the clamped forward parts and the
    -- returns' shares of a part (rule 10) provably keep
    CONSTRAINT ck_production_receipt_line_uom_factor CHECK (uom_numerator > 0 AND uom_denominator > 0 AND uom_factor_source IN ('identity', 'item', 'product', 'global')
        AND (uom_factor_source <> 'identity' OR (uom_numerator = 1 AND uom_denominator = 1))),
    CONSTRAINT ck_production_receipt_line_uom_quantity CHECK (abs(inventory_quantity * uom_denominator - quantity * uom_numerator) <= 2 * uom_denominator
        AND (uom_factor_source <> 'identity' OR inventory_quantity = quantity))
);
-- Backflushed and processor-consumed component lines, generated at Post by production.contract.record_operation_progress
-- or the receipt's backflush, keyed by the calling posting document. One table (holistic decision 11) replaces
-- operation_confirmation_component and production_receipt_component (ADR-0034 rules 12-13; ADR-0037 rule 5; INV-112).
CREATE TABLE operation_progress_component (
    id                             uuid PRIMARY KEY,
    company_id                     uuid NOT NULL,
    production_order_id            uuid NOT NULL,
    operation_confirmation_id      uuid,                       -- calling document: a confirmation,
    production_receipt_id          uuid,                       -- a receipt (backflush_at_receipt),
    service_receipt_id             uuid,                       -- or purchasing's service receipt (no DDL yet; keyed to the document row)
    production_order_component_id  uuid NOT NULL,
    item_id                        uuid NOT NULL,
    warehouse_id                   uuid NOT NULL,              -- the production warehouse, or the processor location
    quantity                       types.quantity NOT NULL CONSTRAINT ck_operation_progress_component_quantity CHECK (quantity > 0),   -- as entered, in uom_id (ADR-0056 rule 9)
    uom_id                         uuid NOT NULL REFERENCES uom (id),
    uom_numerator                  bigint NOT NULL,             -- the conversion snapshot: 1 uom_id = uom_numerator / uom_denominator
    uom_denominator                bigint NOT NULL,             -- inventory units, taken when the unit was set, never re-read (ADR-0056 rule 9)
    uom_factor_source              text NOT NULL,               -- identity, item, product or global (ADR-0056 rule 6)
    inventory_quantity             types.quantity NOT NULL CONSTRAINT ck_operation_progress_component_inventory_quantity CHECK (inventory_quantity > 0),
    lot_id                         uuid REFERENCES lot (id),   -- backflush never takes serials (serial_component_backflush)
    bin_id                         uuid NOT NULL,              -- the supply bin, or the processor's default bin
    cost_object_id                 uuid NOT NULL,
    material_document_line_id      uuid NOT NULL REFERENCES material_document_line (id),   -- movement type production_issue
    recorded_at                    timestamptz NOT NULL,
    CONSTRAINT fk_operation_progress_component_confirmation FOREIGN KEY (company_id, operation_confirmation_id, production_order_id) REFERENCES operation_confirmation (company_id, id, production_order_id),
    CONSTRAINT fk_operation_progress_component_receipt FOREIGN KEY (company_id, production_receipt_id, production_order_id) REFERENCES production_receipt (company_id, id, production_order_id),
    CONSTRAINT fk_operation_progress_component_service_receipt FOREIGN KEY (company_id, service_receipt_id) REFERENCES document (company_id, id),
    CONSTRAINT fk_operation_progress_component_component FOREIGN KEY (company_id, production_order_component_id, production_order_id, item_id, warehouse_id)
        REFERENCES production_order_component (company_id, id, production_order_id, component_item_id, issue_warehouse_id),
    CONSTRAINT fk_operation_progress_component_bin FOREIGN KEY (bin_id, warehouse_id) REFERENCES bin (id, warehouse_id),
    CONSTRAINT fk_operation_progress_component_cost_object FOREIGN KEY (company_id, production_order_id, cost_object_id) REFERENCES production_order (company_id, id, cost_object_id),
    CONSTRAINT ck_operation_progress_component_caller CHECK (num_nonnulls(operation_confirmation_id, production_receipt_id, service_receipt_id) = 1),
    -- the line unit block (ADR-0056 rule 9): a known source, identity only at 1/1, and the inventory quantity within two
    -- inventory units of the exact conversion: a gross-error check that per-line rounding, the clamped forward parts and the
    -- returns' shares of a part (rule 10) provably keep
    CONSTRAINT ck_operation_progress_component_uom_factor CHECK (uom_numerator > 0 AND uom_denominator > 0 AND uom_factor_source IN ('identity', 'item', 'product', 'global')
        AND (uom_factor_source <> 'identity' OR (uom_numerator = 1 AND uom_denominator = 1))),
    CONSTRAINT ck_operation_progress_component_uom_quantity CHECK (abs(inventory_quantity * uom_denominator - quantity * uom_numerator) <= 2 * uom_denominator
        AND (uom_factor_source <> 'identity' OR inventory_quantity = quantity)),
    -- generated backflush lines are written in the inventory unit (ADR-0056 rule 9)
    CONSTRAINT ck_operation_progress_component_uom_identity CHECK (uom_factor_source = 'identity')
);
CREATE INDEX ix_operation_progress_component_component ON operation_progress_component (production_order_component_id);

-- ===== Costing [production] (ADR-0035) =====
CREATE TABLE cost_estimate (                               -- benchmark for target cost and variances; never values stock (rule 14)
    id                             uuid PRIMARY KEY,
    company_id                     uuid NOT NULL,
    production_version_id          uuid NOT NULL,
    item_id                        uuid,                       -- a configured item with the product-level version (ADR-0046 rule 14)
    costing_date                   date NOT NULL,              -- acts as the explosion_date (ADR-0033 rule 5)
    costing_lot_quantity           types.quantity NOT NULL CONSTRAINT ck_cost_estimate_lot CHECK (costing_lot_quantity > 0),   -- holistic decision 18 (ADR-0035 rule 14 note); the command defaults it to the version's minimum lot, else one unit
    state                          text NOT NULL DEFAULT 'draft' CONSTRAINT ck_cost_estimate_state CHECK (state IN ('draft', 'released')),
    price_basis                    text NOT NULL DEFAULT 'actual_average' CONSTRAINT ck_cost_estimate_price_basis CHECK (price_basis IN ('actual_average', 'preliminary_price', 'purchase_price')),   -- flagged default
    bill_of_materials_revision_id  uuid NOT NULL,              -- the revisions it pins (revision_in_use, ADR-0033 rule 4)
    routing_revision_id            uuid,
    company_amount                 types.amount,               -- interim: not stated in ADR-0035 (total for the lot, company currency)
    unit_cost                      types.unit_price,           -- interim: not stated in ADR-0035 (company_amount / costing_lot_quantity; the preliminary price fallback, rule 4)
    released_at                    timestamptz,
    recorded_at                    timestamptz NOT NULL,
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, production_version_id) REFERENCES production_version (company_id, id),
    FOREIGN KEY (company_id, item_id) REFERENCES item (company_id, id),
    FOREIGN KEY (company_id, bill_of_materials_revision_id) REFERENCES bill_of_materials_revision (company_id, id),
    FOREIGN KEY (company_id, routing_revision_id) REFERENCES routing_revision (company_id, id),
    CONSTRAINT ck_cost_estimate_released CHECK ((state = 'released') = (released_at IS NOT NULL AND company_amount IS NOT NULL AND unit_cost IS NOT NULL))
);
-- One released estimate per version and costing date (holistic review); the lookup of the estimate in force uses it too.
CREATE UNIQUE INDEX ux_cost_estimate_released ON cost_estimate (company_id, production_version_id, costing_date) WHERE state = 'released';
CREATE TABLE cost_estimate_line (                          -- rolled up level by level from released estimates of made components (rule 14)
    company_id         uuid NOT NULL,
    cost_estimate_id   uuid NOT NULL,
    line_number        integer NOT NULL CONSTRAINT ck_cost_estimate_line_number CHECK (line_number > 0),
    cost_component     text NOT NULL CONSTRAINT ck_cost_estimate_line_component CHECK (cost_component IN ('material', 'labor', 'overhead', 'other')),
    component_item_id  uuid,
    activity_type_id   uuid,
    cost_center_id     uuid,                                   -- interim: not stated in ADR-0035 (the cost center of an overhead surcharge line)
    quantity           types.quantity NOT NULL,
    price              types.unit_price NOT NULL,
    company_amount     types.amount NOT NULL,
    level              integer NOT NULL DEFAULT 0 CONSTRAINT ck_cost_estimate_line_level CHECK (level >= 0),
    recorded_at        timestamptz NOT NULL,
    PRIMARY KEY (cost_estimate_id, line_number),
    FOREIGN KEY (company_id, cost_estimate_id) REFERENCES cost_estimate (company_id, id),
    FOREIGN KEY (company_id, component_item_id) REFERENCES item (company_id, id),
    FOREIGN KEY (company_id, activity_type_id) REFERENCES activity_type (company_id, id),
    FOREIGN KEY (company_id, cost_center_id) REFERENCES cost_center (company_id, id),
    CONSTRAINT ck_cost_estimate_line_source CHECK (num_nonnulls(component_item_id, activity_type_id, cost_center_id) <= 1
        AND (cost_component <> 'material' OR component_item_id IS NOT NULL)
        AND (activity_type_id IS NULL OR cost_component IN ('labor', 'overhead')))
);
CREATE TABLE activity_rate (                               -- planned rates (rule 14)
    company_id         uuid NOT NULL,
    work_center_id     uuid NOT NULL,
    activity_type_id   uuid NOT NULL,
    posting_period_id  uuid NOT NULL REFERENCES posting_period (id),
    rate               types.unit_price NOT NULL CONSTRAINT ck_activity_rate_rate CHECK (rate >= 0),   -- company currency per activity unit
    recorded_at        timestamptz NOT NULL,
    PRIMARY KEY (work_center_id, activity_type_id, posting_period_id),
    FOREIGN KEY (company_id, work_center_id) REFERENCES work_center (company_id, id),
    FOREIGN KEY (company_id, activity_type_id) REFERENCES activity_type (company_id, id)
);
CREATE TABLE overhead_surcharge (                          -- interim: not stated in ADR-0035 (the table holding "a planned surcharge per cost center", rule 14)
    company_id         uuid NOT NULL,
    cost_center_id     uuid NOT NULL,
    posting_period_id  uuid NOT NULL REFERENCES posting_period (id),
    surcharge_percent  types.percent NOT NULL CONSTRAINT ck_overhead_surcharge_percent CHECK (surcharge_percent >= 0),
    recorded_at        timestamptz NOT NULL,
    PRIMARY KEY (cost_center_id, posting_period_id),
    FOREIGN KEY (company_id, cost_center_id) REFERENCES cost_center (company_id, id)
);
CREATE TABLE pool_allocation_rule (                        -- one rule per (cost center, group) (rules 7, 17)
    company_id        uuid NOT NULL,
    cost_center_id    uuid NOT NULL,
    pool_group        text NOT NULL CONSTRAINT ck_pool_allocation_rule_group CHECK (pool_group IN ('labor', 'overhead', 'other')),
    driver            text NOT NULL CONSTRAINT ck_pool_allocation_rule_driver CHECK (driver IN ('activity_type', 'output_quantity', 'standard_material_quantity', 'preliminary_material_amount')),
    activity_type_id  uuid,                                    -- recorded on the cost center's work centers
    recorded_at       timestamptz NOT NULL,
    PRIMARY KEY (cost_center_id, pool_group),
    FOREIGN KEY (company_id, cost_center_id) REFERENCES cost_center (company_id, id),
    FOREIGN KEY (company_id, activity_type_id) REFERENCES activity_type (company_id, id),
    CONSTRAINT ck_pool_allocation_rule_activity CHECK ((driver = 'activity_type') = (activity_type_id IS NOT NULL))
);
CREATE TABLE normal_capacity (                             -- per (cost center, driver, period) in the driver's unit (rule 7)
    company_id         uuid NOT NULL,
    cost_center_id     uuid NOT NULL,
    driver             text NOT NULL CONSTRAINT ck_normal_capacity_driver CHECK (driver IN ('activity_type', 'output_quantity', 'standard_material_quantity', 'preliminary_material_amount')),
    activity_type_id   uuid,
    posting_period_id  uuid NOT NULL REFERENCES posting_period (id),
    quantity           types.quantity NOT NULL CONSTRAINT ck_normal_capacity_quantity CHECK (quantity > 0),
    recorded_at        timestamptz NOT NULL,
    UNIQUE NULLS NOT DISTINCT (cost_center_id, driver, activity_type_id, posting_period_id),
    FOREIGN KEY (company_id, cost_center_id) REFERENCES cost_center (company_id, id),
    FOREIGN KEY (company_id, activity_type_id) REFERENCES activity_type (company_id, id),
    CONSTRAINT ck_normal_capacity_activity CHECK ((driver = 'activity_type') = (activity_type_id IS NOT NULL))
);
CREATE TABLE production_cost_settlement (                  -- one internal document per run of the period-end job (rule 5)
    id                 uuid PRIMARY KEY,
    company_id         uuid NOT NULL,
    posting_period_id  uuid NOT NULL REFERENCES posting_period (id),
    recorded_at        timestamptz NOT NULL,
    UNIQUE (company_id, id),
    FOREIGN KEY (company_id, id) REFERENCES document (company_id, id)
);
CREATE TABLE production_cost_settlement_line (             -- keyed by (cost object, cost component, step); reruns post differences per key (rule 5)
    company_id                     uuid NOT NULL,
    production_cost_settlement_id  uuid NOT NULL,
    cost_object_id                 uuid NOT NULL REFERENCES cost_object (id),
    cost_component                 text NOT NULL CONSTRAINT ck_production_cost_settlement_line_component CHECK (cost_component IN ('material', 'labor', 'overhead', 'other')),
    step                           text NOT NULL CONSTRAINT ck_production_cost_settlement_line_step CHECK (step IN (     -- the posting order of rule 12
                                       'issue_revaluation', 'pool_allocation', 'unabsorbed_overhead', 'abnormal_cost', 'residual_cost', 'wip_transfer', 'receipt_revaluation')),
    company_amount                 types.amount NOT NULL,
    recorded_at                    timestamptz NOT NULL,
    PRIMARY KEY (production_cost_settlement_id, cost_object_id, cost_component, step),
    FOREIGN KEY (company_id, production_cost_settlement_id) REFERENCES production_cost_settlement (company_id, id)
);
CREATE TABLE production_order_period_cost (                -- written only by the job; row source of the cost sheet (rules 12, 16)
    company_id                     uuid NOT NULL,
    production_order_id            uuid NOT NULL,
    posting_period_id              uuid NOT NULL REFERENCES posting_period (id),
    cost_component                 text NOT NULL CONSTRAINT ck_production_order_period_cost_component CHECK (cost_component IN ('material', 'labor', 'overhead', 'other')),
    opening_amount                 types.amount NOT NULL,      -- company currency, as all amounts of this table
    incurred_amount                types.amount NOT NULL,
    abnormal_amount                types.amount NOT NULL,
    residual_amount                types.amount NOT NULL DEFAULT 0,   -- interim: not stated in ADR-0035 (rule 10's residual, which may be negative)
    to_output_amount               types.amount NOT NULL,
    closing_amount                 types.amount NOT NULL,      -- the WIP that INV-106 compares with the balance
    production_cost_settlement_id  uuid NOT NULL,              -- interim: not stated in ADR-0035 (the run that wrote it)
    recorded_at                    timestamptz NOT NULL,
    PRIMARY KEY (production_order_id, posting_period_id, cost_component),
    FOREIGN KEY (company_id, production_order_id) REFERENCES production_order (company_id, id),
    FOREIGN KEY (company_id, production_cost_settlement_id) REFERENCES production_cost_settlement (company_id, id),
    -- pool = opening + incurred; it goes to abnormal, residual, outputs, or stays as WIP (rules 8-11)
    CONSTRAINT ck_production_order_period_cost_balance CHECK (closing_amount = opening_amount + incurred_amount - abnormal_amount - residual_amount - to_output_amount)
);

-- ===== Revision immutability (ADR-0033 rules 3, 9; ADR-0035 rule 14) =====
CREATE FUNCTION production_revision_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF OLD.state = 'released' THEN RAISE EXCEPTION 'revision_released' USING ERRCODE = 'check_violation'; END IF;
    IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER trg_bill_of_materials_revision_guard BEFORE UPDATE OR DELETE ON bill_of_materials_revision
    FOR EACH ROW EXECUTE FUNCTION production_revision_guard();
CREATE TRIGGER trg_routing_revision_guard BEFORE UPDATE OR DELETE ON routing_revision
    FOR EACH ROW EXECUTE FUNCTION production_revision_guard();
CREATE TRIGGER trg_cost_estimate_guard BEFORE UPDATE OR DELETE ON cost_estimate
    FOR EACH ROW EXECUTE FUNCTION production_revision_guard();
-- Content rows of a released parent never change: TG_ARGV[0] is the parent table, TG_ARGV[1] the parent key column.
-- An update checks the parent the row leaves as well as the one it joins.
CREATE FUNCTION production_revision_content_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE v_state text;
BEGIN
    IF TG_OP IN ('UPDATE', 'DELETE') THEN
        EXECUTE format('SELECT state FROM %I WHERE id = $1', TG_ARGV[0]) INTO v_state USING (to_jsonb(OLD) ->> TG_ARGV[1])::uuid;
        IF v_state = 'released' THEN RAISE EXCEPTION 'revision_released' USING ERRCODE = 'check_violation'; END IF;
    END IF;
    IF TG_OP IN ('INSERT', 'UPDATE') THEN
        EXECUTE format('SELECT state FROM %I WHERE id = $1', TG_ARGV[0]) INTO v_state USING (to_jsonb(NEW) ->> TG_ARGV[1])::uuid;
        IF v_state = 'released' THEN RAISE EXCEPTION 'revision_released' USING ERRCODE = 'check_violation'; END IF;
    END IF;
    IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER trg_bill_of_materials_component_guard BEFORE INSERT OR UPDATE OR DELETE ON bill_of_materials_component
    FOR EACH ROW EXECUTE FUNCTION production_revision_content_guard('bill_of_materials_revision', 'bill_of_materials_revision_id');
CREATE TRIGGER trg_bill_of_materials_output_guard BEFORE INSERT OR UPDATE OR DELETE ON bill_of_materials_output
    FOR EACH ROW EXECUTE FUNCTION production_revision_content_guard('bill_of_materials_revision', 'bill_of_materials_revision_id');
CREATE TRIGGER trg_routing_operation_guard BEFORE INSERT OR UPDATE OR DELETE ON routing_operation
    FOR EACH ROW EXECUTE FUNCTION production_revision_content_guard('routing_revision', 'routing_revision_id');
CREATE TRIGGER trg_routing_operation_activity_guard BEFORE INSERT OR UPDATE OR DELETE ON routing_operation_activity
    FOR EACH ROW EXECUTE FUNCTION production_revision_content_guard('routing_revision', 'routing_revision_id');
CREATE TRIGGER trg_cost_estimate_line_guard BEFORE INSERT OR UPDATE OR DELETE ON cost_estimate_line
    FOR EACH ROW EXECUTE FUNCTION production_revision_content_guard('cost_estimate', 'cost_estimate_id');

-- ===== Changes to tables of other design items =====
-- cost_object (DS-06, owned by production, ADR-0034 rule 15): the production order key DS-06 left for this module. DS-06
-- holds the composite key (company_id, id, production_order_id), so an order's cost_object_id can only name the cost
-- object of kind production_order that names it.
ALTER TABLE cost_object ADD CONSTRAINT fk_cost_object_production_order FOREIGN KEY (company_id, production_order_id) REFERENCES production_order (company_id, id);
ALTER TABLE production_order ADD CONSTRAINT fk_production_order_cost_object FOREIGN KEY (company_id, cost_object_id, id) REFERENCES cost_object (company_id, id, production_order_id);
-- Columns on tables without a DDL draft, listed for their owners:
--   purchase_request_line, purchase_order_line (DS-22): production_order_operation_id, a B3 column flagged for the author
--     (ADR-0037 rule 4; ADR-0028 rule 2), composite key to production_order_operation (company_id, id).
--   service_receipt (DS-22, purchasing, ADR-0037 rule 5): typed header with yield_quantity, scrap_quantity, is_final and
--     lot_id; its generated component lines live in operation_progress_component above.
--   stock_reservation (DS-42): destination_bin_id and release_sequence passed by production (ADR-0034 rule 9).
