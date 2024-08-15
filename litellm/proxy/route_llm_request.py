from typing import TYPE_CHECKING, Any, Literal, Optional, Union

from fastapi import (
    Depends,
    FastAPI,
    File,
    Form,
    Header,
    HTTPException,
    Path,
    Request,
    Response,
    UploadFile,
    status,
)

import litellm
from litellm._logging import verbose_logger

if TYPE_CHECKING:
    from litellm.router import Router as _Router

    LitellmRouter = _Router
else:
    LitellmRouter = Any


async def route_request(
    data: dict,
    llm_router: Optional[LitellmRouter],
    user_model: Optional[str],
    route_type: Literal[
        "acompletion",
        "atext_completion",
        "aembedding",
        "aimage_generation",
        "aspeech",
        "atranscription",
        "amoderation",
    ],
):
    """
    Common helper to route the request

    """
    router_model_names = llm_router.model_names if llm_router is not None else []

    if "api_key" in data:
        return await getattr(litellm, f"{route_type}")(**data)

    elif "user_config" in data:
        router_config = data.pop("user_config")
        user_router = litellm.Router(**router_config)
        return await getattr(user_router, f"{route_type}")(**data)

    elif (
        "," in data.get("model", "")
        and llm_router is not None
        and route_type == "acompletion"
    ):
        if data.get("fastest_response", False):
            return await llm_router.abatch_completion_fastest_response(**data)
        else:
            models = [model.strip() for model in data.pop("model").split(",")]
            return await llm_router.abatch_completion(models=models, **data)

    elif llm_router is not None:
        if (
            data["model"] in router_model_names
            or data["model"] in llm_router.get_model_ids()
        ):
            return await getattr(llm_router, f"{route_type}")(**data)

        elif (
            llm_router.model_group_alias is not None
            and data["model"] in llm_router.model_group_alias
        ):
            return await getattr(llm_router, f"{route_type}")(**data)

        elif data["model"] in llm_router.deployment_names:
            return await getattr(llm_router, f"{route_type}")(
                **data, specific_deployment=True
            )

        elif data["model"] not in router_model_names:
            if llm_router.router_general_settings.pass_through_all_models:
                return await getattr(litellm, f"{route_type}")(**data)
            elif (
                llm_router.default_deployment is not None
                or len(llm_router.provider_default_deployments) > 0
            ):
                return await getattr(llm_router, f"{route_type}")(**data)

    elif user_model is not None:
        return await getattr(litellm, f"{route_type}")(**data)

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={
            "error": f"{route_type}: Invalid model name passed in model="
            + data.get("model", "")
        },
    )
