from google.api.httpbody_pb2 import HttpBody
from grpclib.server import Stream

from viam.components.service_base import ComponentServiceBase
from viam.errors import ComponentNotFoundError
from viam.media.video import CameraMimeType, RawImage
from viam.proto.component.camera import (
    CameraServiceBase,
    GetImageRequest,
    GetImageResponse,
    GetPointCloudRequest,
    GetPointCloudResponse,
    GetPropertiesRequest,
    GetPropertiesResponse,
    RenderFrameRequest,
)

from .camera import Camera


class CameraService(CameraServiceBase, ComponentServiceBase[Camera]):
    """
    gRPC Service for a generic Camera
    """

    RESOURCE_TYPE = Camera

    async def GetImage(self, stream: Stream[GetImageRequest, GetImageResponse]) -> None:
        request = await stream.recv_message()
        assert request is not None
        name = request.name
        try:
            camera = self.get_component(name)
        except ComponentNotFoundError as e:
            raise e.grpc_error

        timeout = stream.deadline.time_remaining() if stream.deadline else None
        image = await camera.get_image(request.mime_type, timeout=timeout, metadata=stream.metadata)
        try:
            mimetype, is_lazy = CameraMimeType.from_lazy(request.mime_type)
            if CameraMimeType.is_supported(mimetype):
                response_mime = mimetype
            else:
                response_mime = request.mime_type
            response = GetImageResponse(mime_type=response_mime)
            img_bytes = mimetype.encode_image(image)
        finally:
            image.close()
        response.image = img_bytes
        await stream.send_message(response)

    async def RenderFrame(self, stream: Stream[RenderFrameRequest, HttpBody]) -> None:
        request = await stream.recv_message()
        assert request is not None
        name = request.name
        try:
            camera = self.get_component(name)
        except ComponentNotFoundError as e:
            raise e.grpc_error
        try:
            mimetype = CameraMimeType(request.mime_type)
        except ValueError:
            mimetype = CameraMimeType.JPEG
        timeout = stream.deadline.time_remaining() if stream.deadline else None
        image = await camera.get_image(mimetype, timeout=timeout, metadata=stream.metadata)
        try:
            img = mimetype.encode_image(image)
        finally:
            image.close()
        response = HttpBody(data=img, content_type=image.mime_type if isinstance(image, RawImage) else mimetype)
        await stream.send_message(response)

    async def GetPointCloud(self, stream: Stream[GetPointCloudRequest, GetPointCloudResponse]) -> None:
        request = await stream.recv_message()
        assert request is not None
        name = request.name
        try:
            camera = self.get_component(name)
        except ComponentNotFoundError as e:
            raise e.grpc_error
        timeout = stream.deadline.time_remaining() if stream.deadline else None
        pc, mimetype = await camera.get_point_cloud(timeout=timeout, metadata=stream.metadata)
        response = GetPointCloudResponse(mime_type=mimetype, point_cloud=pc)
        await stream.send_message(response)

    async def GetProperties(self, stream: Stream[GetPropertiesRequest, GetPropertiesResponse]) -> None:
        request = await stream.recv_message()
        assert request is not None
        name = request.name
        try:
            camera = self.get_component(name)
        except ComponentNotFoundError as e:
            raise e.grpc_error
        timeout = stream.deadline.time_remaining() if stream.deadline else None
        properties = await camera.get_properties(timeout=timeout, metadata=stream.metadata)
        response = GetPropertiesResponse(
            supports_pcd=properties.supports_pcd,
            intrinsic_parameters=properties.intrinsic_parameters,
            distortion_parameters=properties.distortion_parameters,
        )
        await stream.send_message(response)
