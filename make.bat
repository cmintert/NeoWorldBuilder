@ECHO OFF

pushd %~dp0

REM Command file for Sphinx documentation

if "%SPHINXBUILD%" == "" (
	set SPHINXBUILD=sphinx-build
)
if "%SPHINXAPIDOC%" == "" (
	set SPHINXAPIDOC=sphinx-apidoc
)
set SOURCEDIR=source
set BUILDDIR=build
set SRCDIR=src

%SPHINXBUILD% >NUL 2>NUL
if errorlevel 9009 (
	echo.
	echo.The 'sphinx-build' command was not found. Make sure you have Sphinx
	echo.installed, then set the SPHINXBUILD environment variable to point
	echo.to the full path of the 'sphinx-build' executable. Alternatively you
	echo.may add the Sphinx directory to PATH.
	echo.
	echo.If you don't have Sphinx installed, grab it from
	echo.https://www.sphinx-doc.org/
	exit /b 1
)

if "%1" == "" goto help
if "%1" == "clean-api" goto clean-api
if "%1" == "apidoc" goto apidoc
if "%1" == "clean-html" goto clean-html
if "%1" == "rebuild" goto rebuild

%SPHINXBUILD% -M %1 %SOURCEDIR% %BUILDDIR% %SPHINXOPTS% %O%
goto end

:help
%SPHINXBUILD% -M help %SOURCEDIR% %BUILDDIR% %SPHINXOPTS% %O%
echo.
echo.Additional commands:
echo.  clean-api   Remove auto-generated API documentation
echo.  apidoc      Generate API documentation from source code
echo.  clean-html  Remove HTML build
echo.  rebuild     Rebuild everything from scratch
goto end

:clean-api
echo Cleaning auto-generated API documentation...
if exist %SOURCEDIR%\api rmdir /s /q %SOURCEDIR%\api
echo API documentation cleaned
goto end

:apidoc
call :clean-api
echo Generating API documentation...
%SPHINXAPIDOC% -f -o %SOURCEDIR%/api %SRCDIR% --separate --module-first
echo API documentation generated in %SOURCEDIR%/api/
goto end

:clean-html
echo Cleaning HTML build...
if exist %BUILDDIR%\html rmdir /s /q %BUILDDIR%\html
echo HTML build cleaned
goto end

:rebuild
call :clean-api
call :clean-html
echo Generating API documentation...
%SPHINXAPIDOC% -f -o %SOURCEDIR%/api %SRCDIR% --separate --module-first
echo Building HTML documentation...
%SPHINXBUILD% -M html %SOURCEDIR% %BUILDDIR% %SPHINXOPTS% %O%
echo.
echo Documentation rebuilt from scratch in %BUILDDIR%/html/
goto end

:end
popd
