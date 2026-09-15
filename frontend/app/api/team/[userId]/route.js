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


export async function PATCH(
    request,
    { params }
) {
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

        const { userId } = await params;

        if (!userId) {
            return NextResponse.json(
                {
                    detail:
                        "Team member ID is required.",
                },
                {
                    status: 400,
                }
            );
        }

        const body = await request.json();

        const response = await fetch(
            `${getApiUrl()}/api/team/${encodeURIComponent(
                userId
            )}`,
            {
                method: "PATCH",
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
            "Team PATCH proxy error:",
            error
        );

        return NextResponse.json(
            {
                detail:
                    "Unable to update team member.",
            },
            {
                status: 500,
            }
        );
    }
}
