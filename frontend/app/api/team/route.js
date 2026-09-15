import { NextResponse } from "next/server";
import { cookies } from "next/headers";

const COOKIE_NAME = "chairtime_token";


async function getAuthToken() {
    const cookieStore = await cookies();

    return cookieStore.get(COOKIE_NAME)?.value || "";
}


function getApiUrl() {
    const apiUrl = process.env.CHAIRTIME_API_URL;

    if (!apiUrl) {
        throw new Error(
            "Backend URL is not configured."
        );
    }

    return apiUrl.replace(/\/+$/, "");
}


async function backendResponse(response) {
    const data = await response
        .json()
        .catch(() => ({
            detail: "Unexpected backend response.",
        }));

    return NextResponse.json(
        data,
        {
            status: response.status,
        }
    );
}


export async function GET() {
    try {
        const token = await getAuthToken();

        if (!token) {
            return NextResponse.json(
                {
                    detail:
                        "Authentication is required.",
                },
                {
                    status: 401,
                }
            );
        }

        const response = await fetch(
            `${getApiUrl()}/api/team`,
            {
                method: "GET",
                headers: {
                    Accept: "application/json",
                    Authorization: `Bearer ${token}`,
                },
                cache: "no-store",
            }
        );

        return backendResponse(response);
    } catch (error) {
        console.error(
            "Team GET proxy error:",
            error
        );

        return NextResponse.json(
            {
                detail:
                    "Unable to load team members.",
            },
            {
                status: 500,
            }
        );
    }
}


export async function POST(request) {
    try {
        const token = await getAuthToken();

        if (!token) {
            return NextResponse.json(
                {
                    detail:
                        "Authentication is required.",
                },
                {
                    status: 401,
                }
            );
        }

        const body = await request.json();

        const response = await fetch(
            `${getApiUrl()}/api/team`,
            {
                method: "POST",
                headers: {
                    Accept: "application/json",
                    "Content-Type":
                        "application/json",
                    Authorization: `Bearer ${token}`,
                },
                body: JSON.stringify(body),
                cache: "no-store",
            }
        );

        return backendResponse(response);
    } catch (error) {
        console.error(
            "Team POST proxy error:",
            error
        );

        return NextResponse.json(
            {
                detail:
                    "Unable to create team member.",
            },
            {
                status: 500,
            }
        );
    }
}
