from conans import ConanFile, CMake, tools
import os

class LibreSSLConan(ConanFile):
    name = "libressl"
    version = "2.9.2"
    author = "Ralph-Gordon Paul (gordon@rgpaul.com)"
    settings = "os", "compiler", "build_type", "arch"
    options = {"shared": [True, False], "android_ndk": "ANY", "android_stl_type":["c++_static", "c++_shared"]}
    default_options = "shared=False", "android_ndk=None", "android_stl_type=c++_static"
    description = "LibreSSL is a version of the TLS/crypto stack forked from OpenSSL in 2014, with goals of modernizing the codebase, improving security, and applying best practice development processes."
    url = "https://github.com/Manromen/conan-libressl-scripts"
    license = "ISC"
    exports_sources = "cmake-modules/*", "ios/*"

    # download sources
    def source(self):
        url = "https://ftp.openbsd.org/pub/OpenBSD/LibreSSL/libressl-%s.tar.gz" % self.version
        tools.get(url)

    # compile using cmake
    def build(self):
        cmake = CMake(self)
        library_folder = "%s/libressl-%s" % (self.source_folder, self.version)
        cmake.verbose = True

        if self.settings.os == "Android":
            android_toolchain = "cmake-modules/Toolchains/android-cmake/android.toolchain.cmake"
            cmake.definitions["CMAKE_TOOLCHAIN_FILE"] = android_toolchain
            cmake.definitions["ANDROID_NDK"] = os.environ["ANDROID_NDK_PATH"]
            cmake.definitions["ANDROID_ABI"] = tools.to_android_abi(self.settings.arch)
            cmake.definitions["ANDROID_STL"] = self.options.android_stl_type
            cmake.definitions["ANDROID_NATIVE_API_LEVEL"] = self.settings.os.api_level
            cmake.definitions["ANDROID_TOOLCHAIN_NAME"] = "arm-linux-androideabi-4.9"

            cmake.definitions["CMAKE_SYSTEM_NAME"] = "Android"
            cmake.definitions["CMAKE_SYSTEM_VERSION"] = self.settings.os.api_level
            #cmake.definitions["CMAKE_ANDROID_NDK"] = os.environ["ANDROID_NDK_PATH"]
            #cmake.definitions["CMAKE_ANDROID_NDK_TOOLCHAIN_VERSION"] = self.settings.compiler
            #cmake.definitions["CMAKE_ANDROID_STL_TYPE"] = self.options.android_stl_type
            #cmake.definitions["CMAKE_ANDROID_ARCH_ABI"] = tools.to_android_abi(self.settings.arch)

        if self.settings.os == "iOS":
            ios_toolchain = "cmake-modules/Toolchains/ios.toolchain.cmake"
            cmake.definitions["CMAKE_TOOLCHAIN_FILE"] = ios_toolchain
            
            # specify the ios minimum sdk version for crypto
            tools.replace_in_file("%s/libressl-%s/crypto/CMakeLists.txt" % (self.source_folder, self.version),
                        "if (BUILD_SHARED_LIBS)",
                        """set_xcode_property (crypto IPHONEOS_DEPLOYMENT_TARGET "10.0")
                        if (BUILD_SHARED_LIBS) """)

            # specify the ios minimum sdk version for ssl
            tools.replace_in_file("%s/libressl-%s/ssl/CMakeLists.txt" % (self.source_folder, self.version),
                        "if (BUILD_SHARED_LIBS)",
                        """set_xcode_property (ssl IPHONEOS_DEPLOYMENT_TARGET "10.0")
                        if (BUILD_SHARED_LIBS) """)

            # specify the ios minimum sdk version for tls
            tools.replace_in_file("%s/libressl-%s/tls/CMakeLists.txt" % (self.source_folder, self.version),
                        "if (BUILD_SHARED_LIBS)",
                        """set_xcode_property (tls IPHONEOS_DEPLOYMENT_TARGET "10.0")
                        if (BUILD_SHARED_LIBS) """)

            tools.replace_in_file("%s/libressl-%s/CMakeLists.txt" % (self.source_folder, self.version),
                        "project (LibreSSL C ASM)",
                        """project (LibreSSL C ASM)
                        include_directories(BEFORE "ios/include") """)

            cmake.definitions["LIBRESSL_APPS"] = "OFF"
            cmake.definitions["LIBRESSL_TESTS"] = "OFF"
            if self.settings.arch == "x86" or self.settings.arch == "x86_64":
                cmake.definitions["IOS_PLATFORM"] = "SIMULATOR"
            else:
                cmake.definitions["IOS_PLATFORM"] = "OS"

            # define all architectures for ios fat library
            if "arm" in self.settings.arch:
                self.variants = ["armv7", "armv7s", "armv8"]
            else:
                self.variants = []

            # apply build config for all defined architectures
            if len(self.variants) > 0:
                archs = ""
                for i in range(0, len(self.variants)):
                    if i == 0:
                        archs = tools.to_apple_arch(self.variants[i])
                    else:
                        archs += ";" + tools.to_apple_arch(self.variants[i])
                cmake.definitions["CMAKE_OSX_ARCHITECTURES"] = archs
            else:
                cmake.definitions["CMAKE_OSX_ARCHITECTURES"] = tools.to_apple_arch(self.settings.arch)

        if self.settings.os == "Macos":
            cmake.definitions["CMAKE_OSX_ARCHITECTURES"] = tools.to_apple_arch(self.settings.arch)

        cmake.configure(source_folder=library_folder)
        cmake.build()
        cmake.install()

        lib_dir = os.path.join(self.package_folder,"lib")

        # execute ranlib for all static universal libraries (required for fat libraries)
        if self.settings.os == "iOS" and len(self.variants) > 0:
            if self.options.shared == False:
                for f in os.listdir(lib_dir):
                    if f.endswith(".a") and os.path.isfile(os.path.join(lib_dir,f)) and not os.path.islink(os.path.join(lib_dir,f)):
                        self.run("xcrun ranlib %s" % os.path.join(lib_dir,f))

    def package(self):
        self.copy("*", dst="include", src='include')
        self.copy("*.lib", dst="lib", src='lib', keep_path=False)
        self.copy("*.dll", dst="bin", src='bin', keep_path=False)
        self.copy("*.so", dst="lib", src='lib', keep_path=False)
        self.copy("*.dylib", dst="lib", src='lib', keep_path=False)
        self.copy("*.a", dst="lib", src='lib', keep_path=False)
        
    def package_info(self):
        self.cpp_info.libs = tools.collect_libs(self)
        self.cpp_info.includedirs = ['include']

    def package_id(self):
        if "arm" in self.settings.arch and self.settings.os == "iOS":
            self.info.settings.arch = "AnyARM"

    def config_options(self):
        # remove android specific option for all other platforms
        if self.settings.os != "Android":
            del self.options.android_ndk
            del self.options.android_stl_type
