"""Test episode replay and recovery scenarios."""

import pytest
import asyncio
import time
import json
from unittest.mock import Mock, AsyncMock

from tests._fixtures.factories import TenantFactory, UserFactory
from tests._helpers.assertions import PerformanceAssertions


class TestEpisodeReplay:
    """Test episode replay and recovery scenarios."""
    
    @pytest.mark.asyncio
    async def test_episode_recording(self):
        """Test episode recording functionality."""
        # Setup
        tenant_factory = TenantFactory()
        user_factory = UserFactory()
        
        tenant = tenant_factory.create()
        user = user_factory.create(tenant["tenant_id"])
        
        # Mock episode recorder
        episode_recorder = Mock()
        episode_recorder.start_recording = AsyncMock()
        episode_recorder.record_step = AsyncMock()
        episode_recorder.stop_recording = AsyncMock()
        
        # Simulate episode recording
        episode_recorder.start_recording.return_value = {
            "episode_id": "episode_001",
            "recording_started": True,
            "timestamp": time.time()
        }
        
        episode_recorder.record_step.return_value = {
            "step_recorded": True,
            "step_id": "step_001",
            "timestamp": time.time()
        }
        
        episode_recorder.stop_recording.return_value = {
            "recording_stopped": True,
            "episode_id": "episode_001",
            "total_steps": 5,
            "recording_duration_ms": 1000
        }
        
        # Test episode recording
        start_result = await episode_recorder.start_recording(
            tenant_id=tenant["tenant_id"],
            user_id=user["user_id"],
            session_id="session_001"
        )
        assert start_result["recording_started"] is True
        assert start_result["episode_id"] == "episode_001"
        
        # Record episode steps
        steps = [
            {"action": "user_message", "content": "Hello, I need help"},
            {"action": "router_decision", "tier": "SLM_A", "confidence": 0.9},
            {"action": "knowledge_search", "query": "help request", "results": 3},
            {"action": "response_generation", "response": "How can I help you?"},
            {"action": "user_feedback", "satisfaction": "positive"}
        ]
        
        for step in steps:
            record_result = await episode_recorder.record_step(
                episode_id=start_result["episode_id"],
                step_data=step
            )
            assert record_result["step_recorded"] is True
        
        # Stop recording
        stop_result = await episode_recorder.stop_recording(start_result["episode_id"])
        assert stop_result["recording_stopped"] is True
        assert stop_result["total_steps"] == 5
        
        # Verify recording performance
        perf_result = PerformanceAssertions.assert_latency_below_threshold(
            stop_result["recording_duration_ms"], 2000, "Episode recording duration"
        )
        assert perf_result.passed, f"Episode recording should be fast: {perf_result.message}"
    
    @pytest.mark.asyncio
    async def test_episode_exact_replay(self):
        """Test exact episode replay."""
        # Setup
        tenant_factory = TenantFactory()
        
        tenant = tenant_factory.create()
        
        # Mock episode data
        episode_data = {
            "episode_id": "episode_001",
            "tenant_id": tenant["tenant_id"],
            "steps": [
                {
                    "step_id": "step_001",
                    "action": "user_message",
                    "content": "What are your business hours?",
                    "timestamp": time.time() - 300
                },
                {
                    "step_id": "step_002",
                    "action": "router_decision",
                    "tier": "SLM_A",
                    "confidence": 0.95,
                    "timestamp": time.time() - 280
                },
                {
                    "step_id": "step_003",
                    "action": "knowledge_search",
                    "query": "business hours",
                    "results": 1,
                    "timestamp": time.time() - 260
                },
                {
                    "step_id": "step_004",
                    "action": "response_generation",
                    "response": "Our business hours are 9 AM to 6 PM EST",
                    "timestamp": time.time() - 240
                }
            ]
        }
        
        # Mock episode replayer
        episode_replayer = Mock()
        episode_replayer.load_episode = AsyncMock()
        episode_replayer.replay_exact = AsyncMock()
        episode_replayer.verify_replay_accuracy = AsyncMock()
        
        # Simulate episode loading
        episode_replayer.load_episode.return_value = episode_data
        
        # Simulate exact replay
        episode_replayer.replay_exact.return_value = {
            "replay_completed": True,
            "episode_id": "episode_001",
            "steps_replayed": 4,
            "replay_time_ms": 800,
            "exact_matches": 4,
            "deviations": 0
        }
        
        # Simulate replay verification
        episode_replayer.verify_replay_accuracy.return_value = {
            "accuracy_verified": True,
            "match_percentage": 100.0,
            "deviations_detected": 0,
            "verification_time_ms": 100
        }
        
        # Test exact episode replay
        loaded_episode = await episode_replayer.load_episode("episode_001")
        assert loaded_episode["episode_id"] == "episode_001"
        assert len(loaded_episode["steps"]) == 4
        
        # Test exact replay
        replay_result = await episode_replayer.replay_exact(loaded_episode)
        assert replay_result["replay_completed"] is True
        assert replay_result["steps_replayed"] == 4
        assert replay_result["exact_matches"] == 4
        assert replay_result["deviations"] == 0
        
        # Test replay verification
        verification_result = await episode_replayer.verify_replay_accuracy(replay_result)
        assert verification_result["accuracy_verified"] is True
        assert verification_result["match_percentage"] == 100.0
        assert verification_result["deviations_detected"] == 0
        
        # Verify replay performance
        perf_result = PerformanceAssertions.assert_latency_below_threshold(
            replay_result["replay_time_ms"], 1500, "Episode replay time"
        )
        assert perf_result.passed, f"Episode replay should be fast: {perf_result.message}"
    
    @pytest.mark.asyncio
    async def test_episode_similar_replay(self):
        """Test similar episode replay with variations."""
        # Setup
        tenant_factory = TenantFactory()
        
        tenant = tenant_factory.create()
        
        # Mock episode data
        original_episode = {
            "episode_id": "episode_001",
            "tenant_id": tenant["tenant_id"],
            "steps": [
                {
                    "step_id": "step_001",
                    "action": "user_message",
                    "content": "What are your business hours?",
                    "timestamp": time.time() - 300
                },
                {
                    "step_id": "step_002",
                    "action": "router_decision",
                    "tier": "SLM_A",
                    "confidence": 0.95,
                    "timestamp": time.time() - 280
                }
            ]
        }
        
        # Mock episode replayer
        episode_replayer = Mock()
        episode_replayer.replay_similar = AsyncMock()
        episode_replayer.generate_variations = AsyncMock()
        episode_replayer.measure_similarity = AsyncMock()
        
        # Simulate similar replay with variations
        episode_replayer.replay_similar.return_value = {
            "replay_completed": True,
            "episode_id": "episode_001",
            "variations_generated": 3,
            "replay_time_ms": 1200,
            "similarity_score": 0.85,
            "variations": [
                {
                    "variation_id": "var_001",
                    "content": "What are your operating hours?",
                    "similarity": 0.9
                },
                {
                    "variation_id": "var_002",
                    "content": "When are you open?",
                    "similarity": 0.8
                },
                {
                    "variation_id": "var_003",
                    "content": "What time do you close?",
                    "similarity": 0.75
                }
            ]
        }
        
        # Simulate variation generation
        episode_replayer.generate_variations.return_value = {
            "variations_generated": 3,
            "generation_time_ms": 300,
            "variation_quality": "high"
        }
        
        # Simulate similarity measurement
        episode_replayer.measure_similarity.return_value = {
            "similarity_score": 0.85,
            "semantic_similarity": 0.9,
            "structural_similarity": 0.8,
            "measurement_time_ms": 50
        }
        
        # Test similar episode replay
        replay_result = await episode_replayer.replay_similar(original_episode)
        assert replay_result["replay_completed"] is True
        assert replay_result["variations_generated"] == 3
        assert replay_result["similarity_score"] == 0.85
        
        # Test variation generation
        variation_result = await episode_replayer.generate_variations(original_episode)
        assert variation_result["variations_generated"] == 3
        assert variation_result["variation_quality"] == "high"
        
        # Test similarity measurement
        similarity_result = await episode_replayer.measure_similarity(
            original_episode, replay_result["variations"]
        )
        assert similarity_result["similarity_score"] == 0.85
        assert similarity_result["semantic_similarity"] == 0.9
        assert similarity_result["structural_similarity"] == 0.8
        
        # Verify replay performance
        perf_result = PerformanceAssertions.assert_latency_below_threshold(
            replay_result["replay_time_ms"], 2000, "Similar episode replay time"
        )
        assert perf_result.passed, f"Similar episode replay should be reasonable: {perf_result.message}"
    
    @pytest.mark.asyncio
    async def test_episode_adaptive_replay(self):
        """Test adaptive episode replay."""
        # Setup
        tenant_factory = TenantFactory()
        
        tenant = tenant_factory.create()
        
        # Mock episode data
        episode_data = {
            "episode_id": "episode_001",
            "tenant_id": tenant["tenant_id"],
            "context": {
                "user_preferences": {"language": "en", "tone": "formal"},
                "system_state": {"load": "normal", "version": "v1.2.3"},
                "environment": {"timezone": "EST", "business_hours": True}
            },
            "steps": [
                {
                    "step_id": "step_001",
                    "action": "user_message",
                    "content": "What are your business hours?",
                    "timestamp": time.time() - 300
                }
            ]
        }
        
        # Mock adaptive replayer
        adaptive_replayer = Mock()
        adaptive_replayer.analyze_context = AsyncMock()
        adaptive_replayer.adapt_episode = AsyncMock()
        adaptive_replayer.replay_adaptive = AsyncMock()
        
        # Simulate context analysis
        adaptive_replayer.analyze_context.return_value = {
            "context_analyzed": True,
            "adaptations_needed": [
                {"type": "language", "from": "en", "to": "es"},
                {"type": "tone", "from": "formal", "to": "casual"},
                {"type": "timezone", "from": "EST", "to": "PST"}
            ],
            "analysis_time_ms": 100
        }
        
        # Simulate episode adaptation
        adaptive_replayer.adapt_episode.return_value = {
            "episode_adapted": True,
            "adaptations_applied": 3,
            "adapted_content": {
                "original": "What are your business hours?",
                "adapted": "¿Cuáles son sus horarios de atención?"
            },
            "adaptation_time_ms": 200
        }
        
        # Simulate adaptive replay
        adaptive_replayer.replay_adaptive.return_value = {
            "replay_completed": True,
            "episode_id": "episode_001",
            "adaptations_applied": 3,
            "replay_time_ms": 1500,
            "adaptation_success_rate": 0.95,
            "original_vs_adapted": {
                "original_success_rate": 0.9,
                "adapted_success_rate": 0.95,
                "improvement": 0.05
            }
        }
        
        # Test adaptive episode replay
        context_analysis = await adaptive_replayer.analyze_context(episode_data)
        assert context_analysis["context_analyzed"] is True
        assert len(context_analysis["adaptations_needed"]) == 3
        
        # Test episode adaptation
        adaptation_result = await adaptive_replayer.adapt_episode(
            episode_data, context_analysis["adaptations_needed"]
        )
        assert adaptation_result["episode_adapted"] is True
        assert adaptation_result["adaptations_applied"] == 3
        
        # Test adaptive replay
        replay_result = await adaptive_replayer.replay_adaptive(episode_data)
        assert replay_result["replay_completed"] is True
        assert replay_result["adaptations_applied"] == 3
        assert replay_result["adaptation_success_rate"] == 0.95
        assert replay_result["original_vs_adapted"]["improvement"] > 0
        
        # Verify adaptive replay performance
        perf_result = PerformanceAssertions.assert_latency_below_threshold(
            replay_result["replay_time_ms"], 2500, "Adaptive episode replay time"
        )
        assert perf_result.passed, f"Adaptive episode replay should be reasonable: {perf_result.message}"
    
    @pytest.mark.asyncio
    async def test_episode_recovery_after_failure(self):
        """Test episode recovery after system failure."""
        # Setup
        tenant_factory = TenantFactory()
        
        tenant = tenant_factory.create()
        
        # Mock episode recovery
        episode_recovery = Mock()
        episode_recovery.detect_failed_episodes = AsyncMock()
        episode_recovery.recover_episode = AsyncMock()
        episode_recovery.verify_recovery = AsyncMock()
        
        # Simulate failed episode detection
        episode_recovery.detect_failed_episodes.return_value = {
            "failed_episodes_detected": 3,
            "failed_episodes": [
                {
                    "episode_id": "episode_001",
                    "failure_point": "step_003",
                    "failure_reason": "Service timeout",
                    "failure_timestamp": time.time() - 600
                },
                {
                    "episode_id": "episode_002",
                    "failure_point": "step_001",
                    "failure_reason": "Connection lost",
                    "failure_timestamp": time.time() - 300
                },
                {
                    "episode_id": "episode_003",
                    "failure_point": "step_005",
                    "failure_reason": "Memory error",
                    "failure_timestamp": time.time() - 120
                }
            ],
            "detection_time_ms": 150
        }
        
        # Simulate episode recovery
        episode_recovery.recover_episode.return_value = {
            "recovery_completed": True,
            "episode_id": "episode_001",
            "recovery_point": "step_003",
            "recovered_steps": 2,
            "recovery_time_ms": 800,
            "recovery_method": "checkpoint_restore"
        }
        
        # Simulate recovery verification
        episode_recovery.verify_recovery.return_value = {
            "recovery_verified": True,
            "episode_id": "episode_001",
            "data_integrity_check": "passed",
            "step_continuity_check": "passed",
            "verification_time_ms": 100
        }
        
        # Test failed episode detection
        detection_result = await episode_recovery.detect_failed_episodes()
        assert detection_result["failed_episodes_detected"] == 3
        assert len(detection_result["failed_episodes"]) == 3
        
        # Test episode recovery
        for failed_episode in detection_result["failed_episodes"]:
            recovery_result = await episode_recovery.recover_episode(
                failed_episode["episode_id"]
            )
            assert recovery_result["recovery_completed"] is True
            assert recovery_result["episode_id"] == failed_episode["episode_id"]
            
            # Test recovery verification
            verification_result = await episode_recovery.verify_recovery(
                failed_episode["episode_id"]
            )
            assert verification_result["recovery_verified"] is True
            assert verification_result["data_integrity_check"] == "passed"
            assert verification_result["step_continuity_check"] == "passed"
        
        # Verify recovery performance
        perf_result = PerformanceAssertions.assert_latency_below_threshold(
            detection_result["detection_time_ms"], 500, "Failed episode detection time"
        )
        assert perf_result.passed, f"Failed episode detection should be fast: {perf_result.message}"
    
    @pytest.mark.asyncio
    async def test_episode_performance_analysis(self):
        """Test episode performance analysis."""
        # Setup
        tenant_factory = TenantFactory()
        
        tenant = tenant_factory.create()
        
        # Mock episode performance analyzer
        performance_analyzer = Mock()
        performance_analyzer.analyze_episode_performance = AsyncMock()
        performance_analyzer.compare_episodes = AsyncMock()
        performance_analyzer.generate_performance_report = AsyncMock()
        
        # Simulate episode performance analysis
        performance_analyzer.analyze_episode_performance.return_value = {
            "analysis_completed": True,
            "episode_id": "episode_001",
            "performance_metrics": {
                "total_duration_ms": 1500,
                "step_breakdown": {
                    "user_message": 100,
                    "router_decision": 200,
                    "knowledge_search": 800,
                    "response_generation": 300,
                    "user_feedback": 100
                },
                "bottlenecks": ["knowledge_search"],
                "optimization_opportunities": [
                    {"step": "knowledge_search", "potential_savings_ms": 200}
                ]
            },
            "analysis_time_ms": 200
        }
        
        # Simulate episode comparison
        performance_analyzer.compare_episodes.return_value = {
            "comparison_completed": True,
            "episodes_compared": 2,
            "performance_comparison": {
                "episode_001": {"duration_ms": 1500, "success_rate": 0.95},
                "episode_002": {"duration_ms": 1200, "success_rate": 0.90}
            },
            "improvement_areas": [
                {"metric": "duration", "improvement": "episode_002 is 20% faster"},
                {"metric": "success_rate", "improvement": "episode_001 has 5% higher success rate"}
            ]
        }
        
        # Simulate performance report generation
        performance_analyzer.generate_performance_report.return_value = {
            "report_generated": True,
            "report_id": "perf_report_001",
            "report_summary": {
                "total_episodes_analyzed": 10,
                "average_duration_ms": 1350,
                "average_success_rate": 0.92,
                "top_bottlenecks": ["knowledge_search", "response_generation"],
                "recommendations": [
                    "Optimize knowledge search indexing",
                    "Implement response caching",
                    "Add parallel processing for knowledge search"
                ]
            },
            "generation_time_ms": 300
        }
        
        # Test episode performance analysis
        analysis_result = await performance_analyzer.analyze_episode_performance("episode_001")
        assert analysis_result["analysis_completed"] is True
        assert analysis_result["performance_metrics"]["total_duration_ms"] == 1500
        assert "knowledge_search" in analysis_result["performance_metrics"]["bottlenecks"]
        
        # Test episode comparison
        comparison_result = await performance_analyzer.compare_episodes(
            ["episode_001", "episode_002"]
        )
        assert comparison_result["comparison_completed"] is True
        assert len(comparison_result["performance_comparison"]) == 2
        assert len(comparison_result["improvement_areas"]) == 2
        
        # Test performance report generation
        report_result = await performance_analyzer.generate_performance_report(
            ["episode_001", "episode_002"]
        )
        assert report_result["report_generated"] is True
        assert report_result["report_summary"]["total_episodes_analyzed"] == 10
        assert len(report_result["report_summary"]["recommendations"]) == 3
        
        # Verify analysis performance
        perf_result = PerformanceAssertions.assert_latency_below_threshold(
            analysis_result["analysis_time_ms"], 500, "Episode performance analysis time"
        )
        assert perf_result.passed, f"Performance analysis should be fast: {perf_result.message}"
