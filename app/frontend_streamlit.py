"""Streamlit UI that calls the existing FastAPI service over HTTP.

Run from the repository root with:
    python -m streamlit run app/frontend_streamlit.py
"""

# Streamlit basics used in this file:
# - UI calls such as st.button() draw widgets and return their current values.
# - A widget interaction reruns this script from top to bottom.
# - st.form() batches input changes until its submit button is clicked.
# - st.session_state keeps values such as the login token across reruns.
from ast import In
import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import streamlit as st


# Keep configuration in one place. The environment variable lets you use a
# different API without editing this file; local development uses FastAPI's URL.
DEFAULT_API_URL = os.getenv("FASTAPI_BASE_URL", "http://127.0.0.1:8000")
PRODUCTS_PATH = "/api/v1/products"


class APIError(Exception):
    """An API request failed or returned an unexpected response."""


def request_api(
    base_url: str,
    method: str,
    path: str,
    *,
    json_body: dict | None = None,
    form_data: dict[str, str] | None = None,
    token: str | None = None,
) -> object:
    """Send one HTTP request and return decoded JSON, or raise a displayable APIError.

    Pass json_body for product data or form_data for the login endpoint. Keyword-only
    arguments make each request's optional content and token explicit at its call site.
    """
    headers: dict[str, str] = {"Accept": "application/json"}
    body: bytes | None = None

    # FastAPI login reads OAuth2 form fields; product create/update routes read JSON.
    # Content-Type tells FastAPI how to parse the request body.
    if json_body is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(json_body).encode("utf-8")
    elif form_data is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        body = urlencode(form_data).encode("utf-8")

    if token:
        headers["Authorization"] = f"Bearer {token}"

    # urllib builds the HTTP request; GET and DELETE typically have no request body.
    request = Request(
        f"{base_url.rstrip('/')}{path}",
        data=body,
        headers=headers,
        method=method,
    )

    # Normalize HTTP/network failures as APIError so every page can display them
    # through the same helper instead of duplicating error-rendering code.
    try:
        with urlopen(request, timeout=15) as response:
            response_body = response.read()
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        try:
            parsed_detail = json.loads(detail)
            detail = json.dumps(parsed_detail, indent=2)
        except json.JSONDecodeError:
            pass
        raise APIError(f"HTTP {error.code}: {detail or error.reason}") from error
    except URLError as error:
        raise APIError(f"Could not reach the API: {error.reason}") from error
    except TimeoutError as error:
        raise APIError("The API request timed out.") from error

    # DELETE responds with 204 No Content, so there is no JSON response to decode.
    if not response_body:
        return None

    # Decode once here so page code can focus on the UI rather than response parsing.
    try:
        return json.loads(response_body)
    except json.JSONDecodeError as error:
        raise APIError("The API returned a response that was not valid JSON.") from error


def show_result(result: object) -> None:
    """Render a successful response; None means the API returned no response body."""
    if result is None:
        st.success("Request completed successfully.")
    else:
        st.success("Request completed successfully.")
        st.json(result)


def show_api_error(error: APIError) -> None:
    """Keep request failures visible in the UI instead of hiding API details."""
    st.error(str(error))


def product_fields(prefix: str) -> dict:
    """Collect product properties and return a payload ready for create or update.

    Streamlit widgets return their current values. The prefix makes each widget's
    key unique when this helper is reused for create, PUT, and PATCH forms.
    """
    name = st.text_input("Name", max_chars=20, key=f"{prefix}_name")
    description = st.text_input(
        "Description (optional)", max_chars=200, key=f"{prefix}_description"
    )
    price = st.number_input(
        "Price",
        min_value=0.01,
        max_value=9999.99,
        value=1.0,
        step=0.01,
        key=f"{prefix}_price",
    )
    stock_quantity = st.number_input(
        "Stock quantity",
        min_value=0,
        max_value=1000,
        value=0,
        step=1,
        key=f"{prefix}_stock",
    )
    is_active = st.checkbox("Active", value=True, key=f"{prefix}_active")
    return {
        "name": name.strip(),
        "description": description.strip() or None,
        "price": price,
        "stock_quantity": stock_quantity,
        "is_active": is_active,
    }


# Page configuration must be the first Streamlit command. The title/caption are
# display elements; layout="wide" gives the CRUD forms more horizontal space.
st.set_page_config(page_title="Product API frontend", page_icon="📦", layout="wide")
st.title("Product API")
st.caption("A lightweight Streamlit frontend for the existing FastAPI backend.")

# A `with` block places widgets in the sidebar container. The URL input's returned
# string is used as the base address for API calls throughout this script run.
with st.sidebar:
    st.header("API connection")
    api_url = st.text_input("FastAPI base URL", value=DEFAULT_API_URL).strip()
    st.caption("Start FastAPI first. Default: http://127.0.0.1:8000")
    st.divider()
    st.subheader("Authentication")

    # A form batches its inputs: typing doesn't submit the login request; clicking
    # the submit button returns all current values and sets login_submitted to True.
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        login_submitted = st.form_submit_button("Log in")

    if login_submitted:
        # FastAPI's OAuth2 login expects URL-encoded form fields, not JSON. After
        # validating locally, keep the returned token in session state across reruns.
        if not api_url:
            st.error("Enter the FastAPI base URL.")
        elif not username or not password:
            st.error("Enter both username and password.")
        else:
            try:
                login_result = request_api(
                    api_url,
                    "POST",
                    "/api/v1/login/createtoken",
                    form_data={"username": username, "password": password},
                )
                if not isinstance(login_result, dict) or not login_result.get(
                    "access_token"
                ):
                    raise APIError("The login response did not include an access token.")
                st.session_state["api_token"] = login_result["access_token"]
                st.success("Logged in.")
            except APIError as error:
                show_api_error(error)

    if st.session_state.get("api_token"):
        # Session state survives reruns but is scoped to this browser session rather
        # than saved permanently as a user account or database record.
        st.caption("A bearer token is stored for this Streamlit session.")
        if st.button("Log out"):
            del st.session_state["api_token"]
            # Rerun immediately so the sidebar and protected actions reflect logout.
            st.rerun()

# Read the token after the login handler above has had a chance to set it.
token = st.session_state.get("api_token")

# Tabs group controls visually. Each tab is built below; its buttons/forms guard
# their API calls so a normal rerun does not automatically repeat a request.
tabs = st.tabs(["Status", "Browse", "Create", "Update", "Delete", "Filter"])

# A button is True for the rerun caused by its click. Put the request inside this
# condition so page reruns (such as changing a widget) don't call the API again.
with tabs[0]:
    st.subheader("Backend status")
    # Columns are layout containers; each `with` block places a check in its column.
    health_col, ping_col = st.columns(2)
    with health_col:
        if st.button("Check health (GET /)"):
            try:
                show_result(request_api(api_url, "GET", "/"))
            except APIError as error:
                show_api_error(error)
    with ping_col:
        if st.button("Ping (GET /ping)"):
            try:
                show_result(request_api(api_url, "GET", "/ping"))
            except APIError as error:
                show_api_error(error)

with tabs[1]:
    # Read operations don't require a token in this backend. The form prevents
    # submitting the product ID until the user clicks its submit button.
    st.subheader("Browse products")
    if st.button("Load all products"):
        try:
            show_result(request_api(api_url, "GET", PRODUCTS_PATH))
        except APIError as error:
            show_api_error(error)

    with st.form("get_product_form"):
        product_id = st.number_input(
            "Product ID", min_value=1, max_value=1000, value=1, step=1
        )
        get_one_submitted = st.form_submit_button("Get product")
    if get_one_submitted:
        try:
            show_result(
                request_api(api_url, "GET", f"{PRODUCTS_PATH}/{int(product_id)}")
            )
        except APIError as error:
            show_api_error(error)

with tabs[2]:
    # Reuse product_fields() so create and update use the same fields and limits.
    st.subheader("Create a product")
    with st.form("create_product_form"):
        product = product_fields("create")
        create_submitted = st.form_submit_button("Create product")
    if create_submitted:
        if len(product["name"]) < 3:
            st.error("Name must contain at least 3 characters.")
        else:
            try:
                show_result(
                    request_api(
                        api_url,
                        "POST",
                        PRODUCTS_PATH,
                        json_body=product,
                    )
                )
            except APIError as error:
                show_api_error(error)

with tabs[3]:
    # The radio widget returns the chosen mode. PUT replaces all fields; PATCH
    # sends only the fields the user selects below.
    st.subheader("Update a product")
    if not token:
        st.info("Log in in the sidebar before using PUT or PATCH.")

    update_mode = st.radio(
        "Update type",
        ["Replace all fields (PUT)", "Update selected fields (PATCH)"],
        horizontal=True,
    )
    with st.form("update_product_form"):
        # The selected mode determines which form inputs are shown and which
        # fields are included in the eventual request payload.
        update_id = st.number_input(
            "Product ID", min_value=1, max_value=1000, value=1, step=1
        )
        if update_mode == "Replace all fields (PUT)":
            update_product = product_fields("put")
            update_fields: list[str] = []
        else:
            update_fields = st.multiselect(
                "Fields to change",
                ["name", "description", "price", "stock_quantity", "is_active"],
                key="patch_fields",
            )
            update_product = product_fields("patch")
        update_submitted = st.form_submit_button("Save changes")

    if update_submitted:
        if not token:
            st.error("Log in first; PUT and PATCH require a bearer token.")
        elif update_mode == "Replace all fields (PUT)" and len(
            update_product["name"]
        ) < 3:
            st.error("Name must contain at least 3 characters.")
        elif update_mode == "Update selected fields (PATCH)" and not update_fields:
            st.error("Choose at least one field to update.")
        else:
            method = "PUT" if update_mode.startswith("Replace") else "PATCH"
            payload = (
                update_product
                if method == "PUT"
                else {field: update_product[field] for field in update_fields}
            )
            try:
                show_result(
                    request_api(
                        api_url,
                        method,
                        f"{PRODUCTS_PATH}/{int(update_id)}",
                        json_body=payload,
                        token=token,
                    )
                )
            except APIError as error:
                show_api_error(error)

with tabs[4]:
    # Require explicit confirmation before issuing this destructive DELETE request.
    st.subheader("Delete a product")
    with st.form("delete_product_form"):
        delete_id = st.number_input(
            "Product ID", min_value=1, max_value=1000, value=1, step=1
        )
        confirm_delete = st.checkbox("I understand this permanently deletes the product.")
        delete_submitted = st.form_submit_button("Delete product")
    if delete_submitted:
        if not confirm_delete:
            st.error("Confirm the deletion before submitting.")
        else:
            try:
                show_result(
                    request_api(
                        api_url, "DELETE", f"{PRODUCTS_PATH}/{int(delete_id)}"
                    )
                )
            except APIError as error:
                show_api_error(error)

with tabs[5]:
    # Widgets collect filter choices. On submission, urlencode safely escapes the
    # query values (including spaces and symbols) for the HTTP request URL.
    st.subheader("Filter products")
    with st.form("filter_products_form"):
        filter_name = st.text_input("Name contains (minimum 3 characters)")
        filter_description = st.text_input(
            "Description contains (minimum 3 characters)"
        )
        filter_min_price = st.number_input(
            "Minimum price", min_value=1.0, max_value=9999.0, value=1.0
        )
        filter_max_price = st.number_input(
            "Maximum price", min_value=1.0, max_value=9999.0, value=9999.0
        )
        active_choice = st.selectbox("Active status", ["Any", "Active", "Inactive"])
        created_after = st.text_input(
            "Created after (optional ISO datetime)",
            placeholder="2026-10-01T00:00:00",
        )
        sort_by = st.selectbox(
            "Sort by",
            ["id", "name", "price", "stock_quantity", "created_at", "updated_at"],
        )
        page_size = st.number_input(
            "Page size", min_value=5, max_value=20, value=8, step=1
        )
        page_no = st.number_input(
            "Page number", min_value=1, max_value=2000, value=1, step=1
        )
        filter_submitted = st.form_submit_button("Apply filters")

    if filter_submitted:
        # Validate locally for quick feedback; FastAPI still validates requests
        # independently and its errors are also shown to the user.
        if filter_name and len(filter_name) < 3:
            st.error("Name filter must contain at least 3 characters.")
        elif filter_description and len(filter_description) < 3:
            st.error("Description filter must contain at least 3 characters.")
        elif filter_min_price > filter_max_price:
            st.error("Minimum price must not exceed maximum price.")
        else:
            # Send sort, price, and pagination defaults on every filter request;
            # add other query parameters only when the user supplies them.
            params: dict[str, str | int | float | bool] = {
                "min_price": filter_min_price,
                "max_price": filter_max_price,
                "sort_by": sort_by,
                "page_size": int(page_size),
                "page_no": int(page_no),
            }
            if filter_name:
                params["name_seq"] = filter_name
            if filter_description:
                params["description_seq"] = filter_description
            if active_choice != "Any":
                params["active_status"] = active_choice == "Active"
            if created_after:
                params["created_after"] = created_after

            try:
                show_result(
                    request_api(
                        api_url,
                        "GET",
                        f"{PRODUCTS_PATH}/filter?{urlencode(params)}",
                    )
                )
            except APIError as error:
                show_api_error(error)





"""
In app/frontend_streamlit.py, st is the usual alias for the Streamlit library (import streamlit as st). These are the Streamlit calls and attributes used in this file, grouped by what they do.

Page layout and text
st.set_page_config(...) — Sets page-level options, such as the browser tab title, icon, and layout. It appears near the top because Streamlit expects it to run before other Streamlit commands.
st.title(...) — Displays the page’s main heading.
st.header(...) — Displays a prominent section heading; here, it labels the API connection controls in the sidebar.
st.subheader(...) — Displays a smaller section heading, such as “Browse products.”
st.caption(...) — Displays small supporting text under a heading or control.
st.divider() — Draws a horizontal separator between groups of controls.
Layout containers
These are used with Python’s with statement to place content in different parts of the page:

st.sidebar — A container for controls in the page’s sidebar. It is a Streamlit object, not a function.
st.tabs([...]) — Creates a row of tabs and returns one container for each tab. with tabs[0]: puts the following code in the first tab.
st.columns(n) — Splits an area into columns and returns their containers. This app uses two columns for the health and ping checks.
st.form("name") — Groups related widgets into a form. While a user edits fields, the form doesn’t submit; its controls are submitted together when the form’s submit button is clicked.
Input widgets
Input widgets display controls and return their current values, which the script then uses to build requests or check user input.

st.text_input(...) — A single-line text field, used for the API URL, login details, names, descriptions, and date input.
st.number_input(...) — A number field with optional minimum, maximum, starting value, and step size. The product ID, price, stock, and pagination fields use it.
st.checkbox(...) — A true/false control, used for product active status and delete confirmation.
st.radio(...) — Lets the user choose one option, used to choose between PUT and PATCH.
st.selectbox(...) — A dropdown for choosing one option, used for active status and sorting.
st.multiselect(...) — Lets the user choose multiple options, used to select which fields to update with PATCH.
Some widgets use a key argument. It gives a widget a stable, unique identity in Streamlit. The product_fields() helper adds a prefix to its keys so its create, PUT, and PATCH fields don’t clash.

Buttons and messages
st.button(...) — Displays a button and returns True on the rerun caused by clicking it. The app puts API calls inside if st.button(...): so they run only when requested.
st.form_submit_button(...) — Displays a submit button for a form. Its value tells the script whether the user submitted that form in the current rerun.
st.success(...) — Displays a success message.
st.info(...) — Displays an informational message, such as the reminder to log in before updating a product.
st.error(...) — Displays validation or API error messages.
st.json(...) — Displays a response as formatted JSON, useful for viewing product data returned by the backend.
Session state and reruns
st.session_state — Stores values across Streamlit’s full-script reruns for the current browser session. This app stores the login token here. It is an attribute, not a function; for example, st.session_state["api_token"] = token saves a value, and st.session_state.get("api_token") retrieves it.
st.rerun() — Stops the current run and starts the script again immediately. The logout button uses it after clearing the saved token so the page updates to the logged-out state.
The key Streamlit idea
Streamlit scripts run from top to bottom again after interactions. Regular widgets can trigger reruns as their values change; forms batch changes until submission. In this app, button and form-submit checks control when HTTP requests are sent, while session state preserves the login token between reruns.

The HTTP requests themselves use Python’s urllib utilities in this file, not st. functions. st. is used to build the interface and keep track of its state.
"""