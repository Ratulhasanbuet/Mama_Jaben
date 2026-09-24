# Generated manually for PL/pgSQL Coupon Procedures and Triggers

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0011_remove_passenger_shared_passengers_and_more'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                -- 1. Function to determine Passenger Category based on Rides and Spend
                CREATE
                OR REPLACE FUNCTION fn_get_passenger_category(p_user_id INT)
            RETURNS VARCHAR AS $$
            DECLARE
                v_ride_count INT := 0;
                v_total_spend
                DECIMAL(10,2) := 0.00;
                BEGIN
                -- Count completed ride requests
                SELECT COUNT(*)
                INTO v_ride_count
                FROM accounts_riderequest
                WHERE passenger_id = p_user_id
                  AND status IN ('Completed', 'Accepted');

                -- Calculate total paid amount
                SELECT COALESCE(SUM(amount), 0.00)
                INTO v_total_spend
                FROM accounts_payment
                WHERE passenger_id = p_user_id
                  AND status = 'Paid';

                -- Determine Category
                IF
                v_ride_count >= 15 OR v_total_spend >= 3000.00 THEN
                    RETURN 'VIP';
                ELSIF
                v_ride_count >= 5 OR v_total_spend >= 1000.00 THEN
                    RETURN 'REGULAR';
                ELSE
                    RETURN 'NEWBIE';
                END IF;
                END;
            $$
                LANGUAGE plpgsql;

            -- 2. Stored Procedure/Function to distribute coupons by passenger category
            CREATE
                OR REPLACE FUNCTION sp_assign_coupons_by_category(
                p_prefix VARCHAR,
                p_discount DECIMAL,
                p_max_discount DECIMAL,
                p_valid_days INT,
                p_target_category VARCHAR
            )
            RETURNS INT AS $$
            DECLARE
                r RECORD;
                v_cat
                VARCHAR(20);
                v_code
                VARCHAR(30);
                v_assigned_count
                INT := 0;
                BEGIN
                FOR r IN
                SELECT user_id
                FROM accounts_passenger LOOP v_cat := fn_get_passenger_category(r.user_id);

                IF
                p_target_category = 'ALL' OR v_cat = UPPER(p_target_category) THEN
                        -- Check if passenger already has active unused coupon with this prefix
                        IF NOT EXISTS (
                            SELECT 1 FROM accounts_coupon 
                            WHERE passenger_id = r.user_id 
                              AND code LIKE (p_prefix || '-%') 
                              AND is_used = FALSE 
                              AND expire_date >= CURRENT_DATE
                        ) THEN
                            -- Generate code: PREFIX-USERID-RANDOM4
                            v_code := UPPER(p_prefix) || '-' || r.user_id || '-' || UPPER(SUBSTRING(MD5(RANDOM()::TEXT) FROM 1 FOR 4));

                INSERT INTO accounts_coupon (code, expire_date, discount, max_discount, category_target, is_used,
                                             created_at, passenger_id)
                VALUES (v_code, CURRENT_DATE + p_valid_days, p_discount, p_max_discount, v_cat, FALSE, CURRENT_DATE,
                        r.user_id);

                v_assigned_count
                := v_assigned_count + 1;
                END IF;
                END IF;
                END LOOP;

                RETURN v_assigned_count;
                END;
            $$
                LANGUAGE plpgsql;

            -- 3. Function to calculate valid coupon discount amount
            CREATE
                OR REPLACE FUNCTION fn_calculate_coupon_discount(
                p_code VARCHAR,
                p_fare DECIMAL
            )
            RETURNS DECIMAL AS $$
            DECLARE
                v_discount_pct DECIMAL(5,2);
                v_max_disc
                DECIMAL(10,2);
                v_calc_disc
                DECIMAL(10,2);
                BEGIN
                SELECT discount, max_discount
                INTO v_discount_pct, v_max_disc
                FROM accounts_coupon
                WHERE code = p_code
                  AND is_used = FALSE
                  AND expire_date >= CURRENT_DATE;

                IF
                NOT FOUND THEN
                    RETURN 0.00;
                END IF;

                v_calc_disc
                := (p_fare * v_discount_pct) / 100.00;

                IF
                v_max_disc > 0.00 AND v_calc_disc > v_max_disc THEN
                    RETURN v_max_disc;
                ELSE
                    RETURN v_calc_disc;
                END IF;
                END;
            $$
                LANGUAGE plpgsql;

            -- 4. Automatic Trigger to grant Welcome Coupon on new Passenger Registration
            CREATE
                OR REPLACE FUNCTION fn_auto_grant_welcome_coupon()
            RETURNS TRIGGER AS $$
            DECLARE
                v_code VARCHAR(30);
                BEGIN
                v_code
                := 'WELCOME-' || NEW.user_id || '-' || UPPER(SUBSTRING(MD5(RANDOM()::TEXT) FROM 1 FOR 4));

                INSERT INTO accounts_coupon (code, expire_date, discount, max_discount, category_target, is_used,
                                             created_at, passenger_id)
                VALUES (v_code, CURRENT_DATE + 30, 10.00, 50.00, 'NEWBIE', FALSE, CURRENT_DATE, NEW.user_id);

                RETURN NEW;
                END;
            $$
                LANGUAGE plpgsql;

                DROP TRIGGER IF EXISTS trg_passenger_welcome_coupon ON accounts_passenger;
                CREATE TRIGGER trg_passenger_welcome_coupon
                    AFTER INSERT
                    ON accounts_passenger
                    FOR EACH ROW
                    EXECUTE FUNCTION fn_auto_grant_welcome_coupon();
                """,
            reverse_sql="""
            DROP TRIGGER IF EXISTS trg_passenger_welcome_coupon ON accounts_passenger;
            DROP FUNCTION IF EXISTS fn_auto_grant_welcome_coupon();
            DROP FUNCTION IF EXISTS fn_calculate_coupon_discount(VARCHAR, DECIMAL);
            DROP FUNCTION IF EXISTS sp_assign_coupons_by_category(VARCHAR, DECIMAL, DECIMAL, INT, VARCHAR);
            DROP FUNCTION IF EXISTS fn_get_passenger_category(INT);
            """
        )
    ]
