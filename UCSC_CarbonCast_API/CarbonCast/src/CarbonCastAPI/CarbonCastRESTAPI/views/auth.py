from ._base import *
from io import BytesIO


def _qrcode_base64(otp_auth_url):
    """Render the OTP provisioning URL as a base64 PNG, in memory.

    In-memory rendering avoids the shared qr_auth.png file in the working
    directory, which raced between concurrent signups/signins.
    """
    buffer = BytesIO()
    qrcode.make(otp_auth_url).save(buffer)
    return base64.b64encode(buffer.getvalue()).decode('utf-8')


class UserAuthenticationEnforcedView(APIView):
    permission_classes = [permissions.AllowAny]

    @swagger_auto_schema(
        responses={
            200: 'HTTP 200 OK - Success response description',
        }
    )

    def get(self, request, *args, **kwargs):
        response = {
            "Authentication required": settings.REQUIRES_AUTH,
            "carbon_cast_version": carbon_cast_version
        }
        return Response(response, status=status.HTTP_200_OK)
    

class LogoutAPIView(APIView):
    permission_classes = permission_classes
    throttle_classes = []

    @swagger_auto_schema(
        responses={
            200: 'HTTP 200 OK - Success response description',
        }
    )

    def post(self, request, *args, **kwargs):
        logout(request)
        response = {
            "logged_out": True,
            "carbon_cast_version": carbon_cast_version
        }
        return Response(response, status=status.HTTP_200_OK)


class SignUpApiView(APIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = UserSerializer
    queryset = UserModel.objects.all()
    throttle_classes = []

    print(settings.DEFAULT_THROTTLE_LIMIT, settings.EXTENDED_THROTTLE_LIMIT)

    @swagger_auto_schema(
        request_body=serializer_class,
        responses={
            201: 'HTTP 201 Created - User successfully registered',
            400: 'HTTP 400 Bad Request - Invalid input data',
            409: 'HTTP 409 Conflict - User with the same email already exists',
        },
    )

    def post(self, request):
        """
        Register a new user.

        :param request: The HTTP POST request with user registration data.
        :return: User registration response.
        """
        serializer = self.serializer_class(data=request.data)
        
        if serializer.is_valid():
            # serializer = self.serializer_class(data=request.data)
            try:
                user = serializer.save()            
                username = request.data.get('username')
                user.username = username
                user.save()

                if username.startswith('Test'):
                    throttle_limit_value = settings.EXTENDED_THROTTLE_LIMIT
                else:
                    throttle_limit_value = settings.DEFAULT_THROTTLE_LIMIT
                # Throttle limits are disabled when the setting is None;
                # throttle_limit is a non-nullable PositiveIntegerField, so
                # saving None raised IntegrityError and broke every signup.
                if throttle_limit_value is not None:
                    throttle_limit = UserThrottleLimit(user=user, throttle_limit=throttle_limit_value)
                    throttle_limit.save()
                    print(f"Throttle Limit: {throttle_limit.throttle_limit}")

                print(f"Username: {user.username}")

                otp_base32 = pyotp.random_base32()
                email = request.data.get('email').lower()
                # username = request.data.get('username')
                password = request.data.get('password')
                otp_auth_url = pyotp.totp.TOTP(otp_base32).provisioning_uri(
                    name=email, issuer_name="carboncast.com")
                user = authenticate(username=username, password=password)
                user.email = email
                user.otp_auth_url = otp_auth_url
                user.otp_base32 = otp_base32
                user.otp_verified = False
                user.password_checked = True
                
                qrcode_image = _qrcode_base64(user.otp_auth_url)
                user.otp_qrcode_image = qrcode_image
                user.save()

                # code to unpack the image on the frontend
                # from PIL import Image
                # from io import BytesIO
                # im = Image.open(BytesIO(base64.b64decode(qrcode_image.encode('utf-8'))))
                # print(im)
                # im.save('image1.png', 'PNG')

                return Response({
                    "status": "success", 
                    'base32': otp_base32, 
                    "otpauth_url": otp_auth_url, 
                    "otp_qrcode_image": qrcode_image,
                    "carbon_cast_version": carbon_cast_version
                    }, 
                    status=status.HTTP_201_CREATED
                )
                
            except Exception as e:
                print(f"{e}")
                return Response({
                    "status": "fail", 
                    "message": "User with that email already exists", 
                    "carbon_cast_version": carbon_cast_version
                    }, 
                    status=status.HTTP_409_CONFLICT
                )
        else:
            return Response({
                "status": "fail", 
                "message": serializer.errors, 
                "carbon_cast_version": carbon_cast_version
                }, 
                status=status.HTTP_400_BAD_REQUEST
            )


class SignInApiView(APIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = UserSerializer
    # queryset = UserModel.objects.all()
    throttle_classes=[]

    @swagger_auto_schema(
        request_body=serializer_class,
        responses={
            200: 'HTTP 200 OK - User successfully authenticated',
            400: 'HTTP 400 Bad Request - Incorrect email or password',
        },
    )

    def post(self, request):
        """
        Authenticate a user.

        :param request: The HTTP POST request with user authentication data.
        :return: User authentication response.
        """
        # print("Request data: ", request.data)
        data = request.data
        # email = data.get('email')
        username = data.get('username')
        password = data.get('password')

        user = authenticate(username=username, password=password)
        # print(user, username, email, password)
        if user is None:
            return Response({
                "status": "fail", 
                "message": "Incorrect email or password"
                }, 
                status=status.HTTP_400_BAD_REQUEST
            )

        if not user.check_password(password):
            return Response({
                "status": "fail", 
                "message": "Incorrect email or password"
                }, 
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = self.serializer_class(user)
        user.otp_verified = False
        user.password_checked = True

        # Users created outside SignUp may have no OTP secret yet; rebuild
        # the provisioning URL rather than crashing on qrcode.make(None)
        if not user.otp_auth_url:
            if not user.otp_base32:
                user.otp_base32 = pyotp.random_base32()
            user.otp_auth_url = pyotp.totp.TOTP(user.otp_base32).provisioning_uri(
                name=user.email, issuer_name="carboncast.com")

        qrcode_image = _qrcode_base64(user.otp_auth_url)
        user.otp_qrcode_image = qrcode_image
        # persist password_checked/otp fields — VerifyOTP rejects users whose
        # password_checked flag was never saved
        user.save()

        return Response({
            "status": "success", 
            "user": serializer.data, 
            "otp_qrcode_image": qrcode_image,
            "carbon_cast_version": carbon_cast_version
        })


class VerifyOTP(APIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = UserSerializer
    queryset = UserModel.objects.all()
    throttle_classes=[]

    @swagger_auto_schema(
        request_body=serializers.Serializer(
            {
                "username": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="The username of the user to verify OTP for.",
                ),
                "token": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description="The OTP token to be verified.",
                ),
            }
        ),
        responses={
            200: 'HTTP 200 OK - OTP verification successful',
            400: 'HTTP 400 Bad Request - OTP verification failed',
            403: 'HTTP 403 Forbidden - User needs to log in first',
            404: 'HTTP 404 Not Found - User with the given username not found',
        },
    )

    def post(self, request):
        """
        Verify OTP for a user.

        :param request: The HTTP POST request with OTP verification data.
        :return: OTP verification response.
        """
        message = "Token is invalid or user doesn't exist"
        data = request.data
        username = data.get('username', None)
        otp_token = data.get('token', None)
        user = UserModel.objects.filter(username=username).first()
        if user == None:
            return Response({
                "status": "fail", 
                "message": f"No user with username: {username} found"
                }, 
                status=status.HTTP_404_NOT_FOUND
            )

        if not user.password_checked:
            return Response({
                "status": "fail", 
                "message": f"You need to login first"
                }, 
                status=status.HTTP_403_FORBIDDEN
            )

        totp = pyotp.TOTP(user.otp_base32)
        if not totp.verify(otp_token):
            return Response({
                "status": "fail", 
                "message": message, 
                "carbon_cast_version": carbon_cast_version
                }, 
                status=status.HTTP_400_BAD_REQUEST
            )
        user.otp_enabled = True
        user.otp_verified = True
        user.save()
        login(request, user)
        
        serializer = self.serializer_class(user)

        return Response({
            'otp_verified': True,
            "user": serializer.data,
            "carbon_cast_version": carbon_cast_version
        })
