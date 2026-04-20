"""旅行规划API路由"""

import asyncio
from fastapi import APIRouter, HTTPException, Request
from ...models.schemas import (
    TripRequest,
    TripPlanResponse,
)
from ...agents.trip_planner_agent import (
    PlanningCancellationToken,
    TripPlanningCancelledError,
    get_trip_planner_agent,
)

router = APIRouter(prefix="/trip", tags=["旅行规划"])


@router.post(
    "/plan",
    response_model=TripPlanResponse,
    summary="生成旅行计划",
    description="根据用户输入的旅行需求,生成详细的旅行计划"
)
async def plan_trip(http_request: Request, request: TripRequest):
    """
    生成旅行计划

    Args:
        request: 旅行请求参数

    Returns:
        旅行计划响应
    """
    try:
        print(f"\n{'='*60}")
        print(f"📥 收到旅行规划请求:")
        print(f"   城市: {request.city}")
        print(f"   日期: {request.start_date} - {request.end_date}")
        print(f"   天数: {request.travel_days}")
        print(f"{'='*60}\n")

        # 获取Agent实例
        print("🔄 获取多智能体系统实例...")
        agent = get_trip_planner_agent()
        cancellation_token = PlanningCancellationToken()

        # 生成旅行计划
        print("🚀 开始生成旅行计划...")
        planning_task = asyncio.create_task(
            asyncio.to_thread(agent.plan_trip, request, cancellation_token)
        )

        while True:
            try:
                trip_plan = await asyncio.wait_for(asyncio.shield(planning_task), timeout=0.2)
                break
            except asyncio.TimeoutError:
                if await http_request.is_disconnected():
                    cancellation_token.cancel("客户端已停止生成请求")
                    print("🛑 检测到客户端已断开连接，停止后续旅行规划流程")
                    raise HTTPException(
                        status_code=499,
                        detail="已停止生成当前行程"
                    )

        print("✅ 旅行计划生成成功,准备返回响应\n")

        if trip_plan.validation_status == "fallback":
            message = "旅行计划生成成功,已启用安全回退方案"
        elif trip_plan.validation_status == "warning":
            message = "旅行计划生成成功,已完成结构校验并记录天气场景告警"
        else:
            message = "旅行计划生成成功"

        return TripPlanResponse(
            success=True,
            message=message,
            data=trip_plan
        )

    except HTTPException:
        raise
    except TripPlanningCancelledError as e:
        print(f"🛑 生成旅行计划已取消: {str(e)}")
        raise HTTPException(
            status_code=499,
            detail="已停止生成当前行程"
        )
    except Exception as e:
        print(f"❌ 生成旅行计划失败: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"生成旅行计划失败: {str(e)}"
        )


@router.get(
    "/health",
    summary="健康检查",
    description="检查旅行规划服务是否正常"
)
async def health_check():
    """健康检查"""
    try:
        # 检查Agent是否可用
        agent = get_trip_planner_agent()

        return {
            "status": "healthy",
            "service": "trip-planner",
            "agent_name": agent.planner_agent.name,
            "tools_count": len(agent.planner_agent.list_tools())
        }
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"服务不可用: {str(e)}"
        )
