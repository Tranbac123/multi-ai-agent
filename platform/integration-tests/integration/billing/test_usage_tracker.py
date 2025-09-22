"""Test usage tracker functionality."""

import pytest
import time
from unittest.mock import Mock, AsyncMock

from apps.billing-service.core.usage_tracker import (
    UsageTracker,
    UsageType,
    UsageRecord,
    UsageLimit,
)


class TestUsageTracker:
    """Test UsageTracker functionality."""

    @pytest.fixture
    def mock_redis(self):
        """Create mock Redis client."""
        redis_client = Mock()
        redis_client.hset = AsyncMock()
        redis_client.expire = AsyncMock()
        redis_client.incrbyfloat = AsyncMock()
        redis_client.lpush = AsyncMock()
        redis_client.ltrim = AsyncMock()
        redis_client.lrange = AsyncMock()
        redis_client.get = AsyncMock()
        redis_client.keys = AsyncMock()
        redis_client.hgetall = AsyncMock()
        return redis_client

    @pytest.fixture
    def usage_tracker(self, mock_redis):
        """Create UsageTracker instance."""
        return UsageTracker(mock_redis)

    @pytest.mark.asyncio
    async def test_record_usage_success(self, usage_tracker, mock_redis):
        """Test successful usage recording."""
        tenant_id = "tenant_123"
        usage_type = UsageType.TOKENS_IN
        quantity = 1000.0
        metadata = {"model": "gpt-4", "request_id": "req_123"}
        
        result = await usage_tracker.record_usage(tenant_id, usage_type, quantity, metadata)
        
        assert result is True
        
        # Verify Redis operations were called
        mock_redis.hset.assert_called()
        mock_redis.expire.assert_called()
        mock_redis.incrbyfloat.assert_called()
        mock_redis.lpush.assert_called()
        mock_redis.ltrim.assert_called()

    @pytest.mark.asyncio
    async def test_record_usage_error_handling(self, usage_tracker, mock_redis):
        """Test usage recording error handling."""
        mock_redis.hset.side_effect = Exception("Redis error")
        
        result = await usage_tracker.record_usage("tenant_123", UsageType.TOKENS_IN, 1000.0)
        
        assert result is False

    @pytest.mark.asyncio
    async def test_record_usage_without_metadata(self, usage_tracker, mock_redis):
        """Test usage recording without metadata."""
        result = await usage_tracker.record_usage("tenant_123", UsageType.API_CALLS, 1.0)
        
        assert result is True

    @pytest.mark.asyncio
    async def test_get_usage_summary_success(self, usage_tracker, mock_redis):
        """Test getting usage summary successfully."""
        tenant_id = "tenant_123"
        usage_type = UsageType.TOKENS_IN
        
        # Mock usage data
        mock_usage_data = [
            {"quantity": 1000, "timestamp": time.time()},
            {"quantity": 2000, "timestamp": time.time()}
        ]
        
        with patch.object(usage_tracker, '_get_usage_data') as mock_get_data:
            mock_get_data.return_value = mock_usage_data
            
            # Mock usage limit
            usage_tracker.usage_limits[f"usage_limit:{tenant_id}:{usage_type.value}"] = UsageLimit(
                tenant_id=tenant_id,
                usage_type=usage_type,
                limit=10000,
                period="monthly",
                reset_time=time.time() + 86400 * 30
            )
            
            # Mock cost calculation
            with patch.object(usage_tracker, '_calculate_cost') as mock_calc_cost:
                mock_calc_cost.return_value = 0.05
                
                summary = await usage_tracker.get_usage_summary(tenant_id, usage_type)
        
        assert summary["tenant_id"] == tenant_id
        assert summary["usage_type"] == usage_type.value
        assert summary["total_usage"] == 3000  # 1000 + 2000
        assert summary["usage_count"] == 2
        assert summary["usage_limit"] == 10000
        assert summary["usage_percentage"] == 30.0  # 3000 / 10000 * 100
        assert summary["cost"] == 0.05

    @pytest.mark.asyncio
    async def test_get_usage_summary_no_limit(self, usage_tracker, mock_redis):
        """Test getting usage summary without usage limit."""
        with patch.object(usage_tracker, '_get_usage_data') as mock_get_data:
            mock_get_data.return_value = [{"quantity": 1000, "timestamp": time.time()}]
            
            with patch.object(usage_tracker, '_calculate_cost') as mock_calc_cost:
                mock_calc_cost.return_value = 0.05
                
                summary = await usage_tracker.get_usage_summary("tenant_123", UsageType.TOKENS_IN)
        
        assert summary["usage_limit"] is None
        assert summary["usage_percentage"] == 0

    @pytest.mark.asyncio
    async def test_get_all_usage_summary_success(self, usage_tracker, mock_redis):
        """Test getting all usage summary successfully."""
        # Mock individual usage summaries
        with patch.object(usage_tracker, 'get_usage_summary') as mock_get_summary:
            mock_get_summary.side_effect = [
                {"cost": 0.05, "total_usage": 1000},
                {"cost": 0.03, "total_usage": 500},
                {"cost": 0.10, "total_usage": 100},
                {"cost": 0.02, "total_usage": 200},
                {"cost": 0.01, "total_usage": 50},
                {"cost": 0.08, "total_usage": 80}
            ]
            
            summary = await usage_tracker.get_all_usage_summary("tenant_123")
        
        assert summary["tenant_id"] == "tenant_123"
        assert summary["total_cost"] == 0.29  # Sum of all costs
        assert len(summary["usage_types"]) == 6  # All UsageType enum values

    @pytest.mark.asyncio
    async def test_check_usage_limit_within_limit(self, usage_tracker, mock_redis):
        """Test checking usage limit when within limit."""
        tenant_id = "tenant_123"
        usage_type = UsageType.TOKENS_IN
        
        # Set usage limit
        usage_tracker.usage_limits[f"usage_limit:{tenant_id}:{usage_type.value}"] = UsageLimit(
            tenant_id=tenant_id,
            usage_type=usage_type,
            limit=10000,
            period="monthly",
            reset_time=time.time() + 86400 * 30
        )
        
        # Mock current usage
        with patch.object(usage_tracker, '_get_current_usage') as mock_get_current:
            mock_get_current.return_value = 5000.0
            
            result = await usage_tracker.check_usage_limit(tenant_id, usage_type, 1000.0)
        
        assert result["within_limit"] is True
        assert result["current_usage"] == 5000.0
        assert result["usage_limit"] == 10000
        assert result["remaining_usage"] == 5000.0
        assert result["projected_usage"] == 6000.0

    @pytest.mark.asyncio
    async def test_check_usage_limit_exceeded(self, usage_tracker, mock_redis):
        """Test checking usage limit when limit would be exceeded."""
        tenant_id = "tenant_123"
        usage_type = UsageType.TOKENS_IN
        
        # Set usage limit
        usage_tracker.usage_limits[f"usage_limit:{tenant_id}:{usage_type.value}"] = UsageLimit(
            tenant_id=tenant_id,
            usage_type=usage_type,
            limit=10000,
            period="monthly",
            reset_time=time.time() + 86400 * 30
        )
        
        # Mock current usage
        with patch.object(usage_tracker, '_get_current_usage') as mock_get_current:
            mock_get_current.return_value = 9500.0
            
            result = await usage_tracker.check_usage_limit(tenant_id, usage_type, 1000.0)
        
        assert result["within_limit"] is False
        assert result["projected_usage"] == 10500.0

    @pytest.mark.asyncio
    async def test_check_usage_limit_no_limit_set(self, usage_tracker, mock_redis):
        """Test checking usage limit when no limit is set."""
        with patch.object(usage_tracker, '_get_current_usage') as mock_get_current:
            mock_get_current.return_value = 5000.0
            
            result = await usage_tracker.check_usage_limit("tenant_123", UsageType.TOKENS_IN)
        
        assert result["within_limit"] is True
        assert result["usage_limit"] is None
        assert result["remaining_usage"] is None

    def test_set_usage_limit_success(self, usage_tracker, mock_redis):
        """Test setting usage limit successfully."""
        tenant_id = "tenant_123"
        usage_type = UsageType.TOKENS_IN
        limit = 10000.0
        period = "monthly"
        
        usage_tracker.set_usage_limit(tenant_id, usage_type, limit, period)
        
        # Check that limit was stored in memory
        limit_key = f"usage_limit:{tenant_id}:{usage_type.value}"
        assert limit_key in usage_tracker.usage_limits
        
        stored_limit = usage_tracker.usage_limits[limit_key]
        assert stored_limit.tenant_id == tenant_id
        assert stored_limit.usage_type == usage_type
        assert stored_limit.limit == limit
        assert stored_limit.period == period

    def test_set_pricing_rate_success(self, usage_tracker, mock_redis):
        """Test setting pricing rate successfully."""
        usage_type = UsageType.TOKENS_IN
        rate = 0.0001
        unit = "per_token"
        
        usage_tracker.set_pricing_rate(usage_type, rate, unit)
        
        # Check that rate was stored
        assert usage_type.value in usage_tracker.pricing_rates
        assert usage_tracker.pricing_rates[usage_type.value]["rate"] == rate
        assert usage_tracker.pricing_rates[usage_type.value]["unit"] == unit

    def test_set_pricing_rate_default_unit(self, usage_tracker, mock_redis):
        """Test setting pricing rate with default unit."""
        usage_type = UsageType.API_CALLS
        rate = 0.10
        
        usage_tracker.set_pricing_rate(usage_type, rate)
        
        assert usage_tracker.pricing_rates[usage_type.value]["rate"] == rate
        assert usage_tracker.pricing_rates[usage_type.value]["unit"] == "per_unit"

    @pytest.mark.asyncio
    async def test_get_usage_data_daily(self, usage_tracker, mock_redis):
        """Test getting daily usage data."""
        mock_redis.get.return_value = b"5000.0"
        
        data = await usage_tracker._get_usage_data("tenant_123", UsageType.TOKENS_IN, "daily")
        
        assert len(data) == 1
        assert data[0]["quantity"] == 5000.0
        assert data[0]["timestamp"] is not None

    @pytest.mark.asyncio
    async def test_get_usage_data_monthly(self, usage_tracker, mock_redis):
        """Test getting monthly usage data."""
        mock_redis.get.return_value = b"10000.0"
        
        data = await usage_tracker._get_usage_data("tenant_123", UsageType.TOKENS_IN, "monthly")
        
        assert len(data) == 1
        assert data[0]["quantity"] == 10000.0

    @pytest.mark.asyncio
    async def test_get_usage_data_yearly(self, usage_tracker, mock_redis):
        """Test getting yearly usage data."""
        mock_redis.get.return_value = b"120000.0"
        
        data = await usage_tracker._get_usage_data("tenant_123", UsageType.TOKENS_IN, "yearly")
        
        assert len(data) == 1
        assert data[0]["quantity"] == 120000.0

    @pytest.mark.asyncio
    async def test_get_usage_data_all_records(self, usage_tracker, mock_redis):
        """Test getting all usage records."""
        # Mock record keys
        mock_redis.lrange.return_value = [
            b"usage_record:tenant_123:tokens_in:1643673600",
            b"usage_record:tenant_123:tokens_in:1643673700"
        ]
        
        # Mock record data
        record_data_1 = {
            b"quantity": b"1000.0",
            b"timestamp": b"1643673600.0"
        }
        record_data_2 = {
            b"quantity": b"2000.0",
            b"timestamp": b"1643673700.0"
        }
        
        mock_redis.hgetall.side_effect = [record_data_1, record_data_2]
        
        data = await usage_tracker._get_usage_data("tenant_123", UsageType.TOKENS_IN, "all")
        
        assert len(data) == 2
        assert data[0]["quantity"] == 2000.0  # Sorted by timestamp
        assert data[1]["quantity"] == 1000.0

    @pytest.mark.asyncio
    async def test_get_current_usage_success(self, usage_tracker, mock_redis):
        """Test getting current usage successfully."""
        mock_redis.get.return_value = b"5000.0"
        
        usage = await usage_tracker._get_current_usage("tenant_123", UsageType.TOKENS_IN)
        
        assert usage == 5000.0

    @pytest.mark.asyncio
    async def test_get_current_usage_no_data(self, usage_tracker, mock_redis):
        """Test getting current usage when no data exists."""
        mock_redis.get.return_value = None
        
        usage = await usage_tracker._get_current_usage("tenant_123", UsageType.TOKENS_IN)
        
        assert usage == 0.0

    @pytest.mark.asyncio
    async def test_calculate_cost_success(self, usage_tracker, mock_redis):
        """Test calculating cost successfully."""
        usage_type = UsageType.TOKENS_IN
        quantity = 1000.0
        
        # Set pricing rate
        usage_tracker.pricing_rates[usage_type.value] = {"rate": 0.0001, "unit": "per_token"}
        
        cost = await usage_tracker._calculate_cost(usage_type, quantity)
        
        assert cost == 0.1  # 1000 * 0.0001

    @pytest.mark.asyncio
    async def test_calculate_cost_no_rate_set(self, usage_tracker, mock_redis):
        """Test calculating cost when no rate is set."""
        cost = await usage_tracker._calculate_cost(UsageType.TOKENS_IN, 1000.0)
        
        assert cost == 0.0

    @pytest.mark.asyncio
    async def test_check_usage_limits_exceeded(self, usage_tracker, mock_redis):
        """Test checking usage limits when exceeded."""
        tenant_id = "tenant_123"
        usage_type = UsageType.TOKENS_IN
        
        # Set usage limit
        usage_tracker.usage_limits[f"usage_limit:{tenant_id}:{usage_type.value}"] = UsageLimit(
            tenant_id=tenant_id,
            usage_type=usage_type,
            limit=10000,
            period="monthly",
            reset_time=time.time() + 86400 * 30
        )
        
        # Mock current usage exceeding limit
        with patch.object(usage_tracker, '_get_current_usage') as mock_get_current:
            mock_get_current.return_value = 15000.0
            
            # Mock alert triggering
            with patch.object(usage_tracker, '_trigger_limit_exceeded_alert') as mock_trigger:
                await usage_tracker._check_usage_limits(tenant_id, usage_type)
                
                mock_trigger.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_usage_limits_within_limit(self, usage_tracker, mock_redis):
        """Test checking usage limits when within limit."""
        tenant_id = "tenant_123"
        usage_type = UsageType.TOKENS_IN
        
        # Set usage limit
        usage_tracker.usage_limits[f"usage_limit:{tenant_id}:{usage_type.value}"] = UsageLimit(
            tenant_id=tenant_id,
            usage_type=usage_type,
            limit=10000,
            period="monthly",
            reset_time=time.time() + 86400 * 30
        )
        
        # Mock current usage within limit
        with patch.object(usage_tracker, '_get_current_usage') as mock_get_current:
            mock_get_current.return_value = 5000.0
            
            # Mock alert triggering
            with patch.object(usage_tracker, '_trigger_limit_exceeded_alert') as mock_trigger:
                await usage_tracker._check_usage_limits(tenant_id, usage_type)
                
                mock_trigger.assert_not_called()

    def test_calculate_reset_time_daily(self, usage_tracker, mock_redis):
        """Test calculating reset time for daily period."""
        reset_time = usage_tracker._calculate_reset_time("daily")
        
        # Should be in the future
        assert reset_time > time.time()
        # Should be within 24 hours
        assert reset_time <= time.time() + 86400

    def test_calculate_reset_time_monthly(self, usage_tracker, mock_redis):
        """Test calculating reset time for monthly period."""
        reset_time = usage_tracker._calculate_reset_time("monthly")
        
        # Should be in the future
        assert reset_time > time.time()
        # Should be within 30 days
        assert reset_time <= time.time() + 86400 * 30

    def test_calculate_reset_time_yearly(self, usage_tracker, mock_redis):
        """Test calculating reset time for yearly period."""
        reset_time = usage_tracker._calculate_reset_time("yearly")
        
        # Should be in the future
        assert reset_time > time.time()
        # Should be within 365 days
        assert reset_time <= time.time() + 86400 * 365

    def test_calculate_reset_time_default(self, usage_tracker, mock_redis):
        """Test calculating reset time for unknown period."""
        reset_time = usage_tracker._calculate_reset_time("unknown")
        
        # Should default to 24 hours
        assert reset_time > time.time()
        assert reset_time <= time.time() + 86400

    def test_usage_type_enum_values(self):
        """Test UsageType enum values."""
        assert UsageType.TOKENS_IN.value == "tokens_in"
        assert UsageType.TOKENS_OUT.value == "tokens_out"
        assert UsageType.TOOL_CALLS.value == "tool_calls"
        assert UsageType.WS_MINUTES.value == "ws_minutes"
        assert UsageType.STORAGE_MB.value == "storage_mb"
        assert UsageType.API_CALLS.value == "api_calls"

    def test_usage_record_creation(self):
        """Test UsageRecord creation."""
        record = UsageRecord(
            tenant_id="tenant_123",
            usage_type=UsageType.TOKENS_IN,
            quantity=1000.0,
            timestamp=time.time(),
            metadata={"model": "gpt-4"}
        )
        
        assert record.tenant_id == "tenant_123"
        assert record.usage_type == UsageType.TOKENS_IN
        assert record.quantity == 1000.0
        assert record.metadata == {"model": "gpt-4"}

    def test_usage_limit_creation(self):
        """Test UsageLimit creation."""
        limit = UsageLimit(
            tenant_id="tenant_123",
            usage_type=UsageType.TOKENS_IN,
            limit=10000.0,
            period="monthly",
            reset_time=time.time() + 86400 * 30
        )
        
        assert limit.tenant_id == "tenant_123"
        assert limit.usage_type == UsageType.TOKENS_IN
        assert limit.limit == 10000.0
        assert limit.period == "monthly"


# Import patch for mocking
from unittest.mock import patch
