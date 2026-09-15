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


export async function POST(
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

        const response = await fetch(
            `${getApiUrl()}/api/team/${encodeURIComponent(
                userId
            )}/activate`,
            {
                method: "POST",
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
            "Team activate proxy error:",
            error
        );

        return NextResponse.json(
            {
                detail:
                    "Unable to activate team member.",
            },
            {
                status: 500,
            }
        );
    }
}
