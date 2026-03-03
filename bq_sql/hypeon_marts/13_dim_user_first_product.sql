-- Marts: first product purchased per user. For "repeat purchase rate + what did they first buy".

CREATE OR REPLACE VIEW `{BQ_PROJECT}.hypeon_marts.dim_user_first_product` AS
WITH first_order AS (
  SELECT user_pseudo_id, transaction_id, order_date,
    ROW_NUMBER() OVER (PARTITION BY user_pseudo_id ORDER BY order_date) AS rn
  FROM `{BQ_PROJECT}.hypeon_marts.fct_orders`
)
SELECT
  o.user_pseudo_id,
  o.order_date AS first_order_date,
  o.transaction_id AS first_transaction_id,
  MIN(i.item_id) AS first_product_id
FROM first_order o
JOIN `{BQ_PROJECT}.hypeon_marts.fct_order_items` i
  ON o.transaction_id = i.transaction_id AND o.user_pseudo_id = i.user_pseudo_id
WHERE o.rn = 1
GROUP BY o.user_pseudo_id, o.order_date, o.transaction_id;
